"""内嵌浏览器登录窗口。

基于 QWebEngineView 直接在应用内完成登录：
- 通过注入 JS 钩住 XMLHttpRequest / fetch，捕获 xkxf.do 请求的
  token 请求头与请求体（xh / xklcdm）；
- 通过 QWebEngineProfile 的 CookieStore 收集站点 Cookie；
- 两者凑齐后组装成与 selenium-wire 嗅探器相同格式的捕获数据。
"""

import json
import os
import re

from PyQt6.QtCore import QRectF, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPainterPath, QRegion
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import BASE_URL, LOGIN_CACHE_DIR, LOGIN_PROFILE_DIR, XKXF_URL
from ..credentials import CredentialError, Credentials

_CAPTURE_PREFIX = "JNU_CAPTURE:"

# 钩住 XHR 与 fetch，命中目标接口时把请求头与请求体打到 console
_HOOK_SCRIPT = """
(function() {
    // 仅在选课系统域注入钩子；统一身份认证 / 滑块验证页面保持原生
    // XHR / fetch，避免反爬风控通过 toString() 检测到原型被改写而判定
    // 环境异常，导致滑块拼图即使拖对也一直验证失败。
    if (location.hostname.indexOf('__TARGET_HOST__') === -1) { return; }
    if (window.__jnuHooked) { return; }
    window.__jnuHooked = true;
    var TARGET = 'xkxf.do';

    var origOpen = XMLHttpRequest.prototype.open;
    var origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
    var origSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url) {
        this.__jnuUrl = url;
        this.__jnuHeaders = {};
        return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.setRequestHeader = function(key, value) {
        try { this.__jnuHeaders[String(key).toLowerCase()] = String(value); } catch (e) {}
        return origSetHeader.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function(body) {
        try {
            if (this.__jnuUrl && String(this.__jnuUrl).indexOf(TARGET) !== -1) {
                console.log('JNU_CAPTURE:' + JSON.stringify({
                    url: String(this.__jnuUrl),
                    headers: this.__jnuHeaders || {},
                    body: body == null ? '' : String(body)
                }));
            }
        } catch (e) {}
        return origSend.apply(this, arguments);
    };

    if (window.fetch) {
        var origFetch = window.fetch;
        window.fetch = function(input, init) {
            try {
                var url = (typeof input === 'string') ? input : (input && input.url) || '';
                if (url.indexOf(TARGET) !== -1) {
                    var headers = {};
                    var rawHeaders = (init && init.headers) || {};
                    if (rawHeaders.forEach) {
                        rawHeaders.forEach(function(v, k) { headers[k.toLowerCase()] = v; });
                    } else {
                        for (var k in rawHeaders) { headers[k.toLowerCase()] = rawHeaders[k]; }
                    }
                    var body = (init && init.body) ? String(init.body) : '';
                    console.log('JNU_CAPTURE:' + JSON.stringify({
                        url: url, headers: headers, body: body
                    }));
                }
            } catch (e) {}
            return origFetch.apply(this, arguments);
        };
    }
})();
"""


class _CapturePage(QWebEnginePage):
    """把 JS 钩子打出的 console 消息转成 Qt 信号。"""

    captured = pyqtSignal(dict)

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        if message.startswith(_CAPTURE_PREFIX):
            try:
                self.captured.emit(json.loads(message[len(_CAPTURE_PREFIX):]))
            except json.JSONDecodeError:
                pass
            return
        super().javaScriptConsoleMessage(level, message, line_number, source_id)


_LOGIN_PROFILE = None


def _calibrate_client_hints(profile, user_agent):
    """对齐 Client Hints 品牌/版本，补上真实 Chrome 才有的 "Google Chrome" 品牌。

    QtWebEngine 默认只上报 "Chromium" + GREASE 品牌，缺少 "Google Chrome"，
    而 UA 字符串里写的是 "Chrome/xxx"。风控一旦比对 UA 与
    navigator.userAgentData.brands 就会发现"自称 Chrome 却无 Google Chrome
    品牌"的矛盾（GOAL.md 根因 #2）。这里采用读-改-写：保留 Qt 既有的
    Chromium / GREASE 品牌（含其特定 greasy 字符串，避免自行伪造产生新破绽），
    只追加 Google Chrome，并把版本号对齐到 UA 的 Chrome 主版本。

    ⚠ 需经 diag_fingerprint.html 验证确实改变了 navigator.userAgentData.brands
    后再依赖；任何异常都吞掉，不能影响登录主流程。
    """
    try:
        match = re.search(r"Chrome/(\d+)", user_agent)
        if not match:
            return
        fallback_version = f"{match.group(1)}.0.0.0"
        hints = profile.clientHints()
        brands = dict(hints.fullVersionList() or {})
        # 真实 Chrome 里 Chromium 与 Google Chrome 的完整版本号完全一致，
        # 因此让 Google Chrome 复用 Chromium 的精确版本（如 140.0.7339.225），
        # 避免高熵 fullVersionList 出现两者版本不一致的破绽。
        chromium_version = next(
            (v for k, v in brands.items() if "chromium" in str(k).lower()),
            None,
        )
        if chromium_version is None:
            brands["Chromium"] = chromium_version = fallback_version
        brands["Google Chrome"] = chromium_version
        hints.setFullVersionList(brands)
    except Exception:  # noqa: BLE001 - 校准失败不应阻断登录
        pass


def _login_profile():
    """进程内共享的持久化登录 profile（单例）。

    为什么是单例：持久化 profile 必须用带 storageName 的构造函数，且同名 +
    同存储路径的 profile 在同一进程内不能并存（cookie 的 SQLite 会被占用、
    Qt 也会告警）。而登录对话框可被多次开关（取消后重试），若每次都新建同名
    持久化 profile 就会冲突。因此全进程共享一个，parent 挂到 QApplication，
    使其贯穿应用生命周期；捕获钩子脚本与 UA / Client Hints 也只配置一次。
    """
    global _LOGIN_PROFILE
    if _LOGIN_PROFILE is not None:
        return _LOGIN_PROFILE

    os.makedirs(LOGIN_PROFILE_DIR, exist_ok=True)
    os.makedirs(LOGIN_CACHE_DIR, exist_ok=True)

    profile = QWebEngineProfile("jnu_login", QApplication.instance())
    profile.setPersistentStoragePath(LOGIN_PROFILE_DIR)
    profile.setCachePath(LOGIN_CACHE_DIR)
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
    )
    # 去掉默认 UA 里的 "QtWebEngine/x.y.z " 标记，得到与底层 Chromium 版本
    # 一致的纯净 Chrome UA：既不暴露嵌入式浏览器身份，又保证 UA 与
    # Client Hints(sec-ch-ua) 版本号一致。该 UA 捕获时随请求头传给抢课端。
    user_agent = re.sub(r"QtWebEngine/\S+\s+", "", profile.httpUserAgent())
    profile.setHttpUserAgent(user_agent)
    # navigator.languages：QtWebEngine 默认 "en"，但本机是中文环境、国内 IP、
    # 访问国内高校站，纯英文语言与时区/IP 自相矛盾，是中文风控引擎(易盾)的明显
    # 异常点（实测真实 Chrome 为 zh-CN）。对齐成简体中文环境：setHttpAcceptLanguage
    # 同时改 Accept-Language 头与页面里的 navigator.languages / navigator.language。
    profile.setHttpAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.8")
    _calibrate_client_hints(profile, user_agent)

    # 捕获钩子脚本只装一次（只在选课域生效，认证 / 滑块页保持原生）
    target_host = QUrl(BASE_URL).host()
    script = QWebEngineScript()
    script.setName("jnu-capture-hook")
    script.setSourceCode(_HOOK_SCRIPT.replace("__TARGET_HOST__", target_host))
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(True)
    profile.scripts().insert(script)

    _LOGIN_PROFILE = profile
    return profile


class EmbeddedLoginDialog(QDialog):
    """内嵌浏览器登录对话框。

    捕获到完整凭据后发出 credentials_captured 并自动关闭。
    """

    credentials_captured = pyqtSignal(object)
    log = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("embeddedLogin")
        self.setWindowTitle("登录选课系统")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)

        # 小屏（如 1366x768）放不下默认尺寸时收缩到可用区域内
        available = self.screen().availableGeometry()
        self.resize(
            min(1080, available.width() - 80),
            min(760, available.height() - 80),
        )

        self._cookies = {}
        self._captured_request = None
        self._done = False

        # 进程内共享的持久化登录 profile（落盘 + 持久 cookie + UA/Client Hints
        # 校准 + 捕获钩子，详见 _login_profile）。持久化让易盾设备指纹跨启动
        # 稳定、积累信誉，降低风控分（GOAL.md 根因 #1）。
        self._profile = _login_profile()
        self._user_agent = self._profile.httpUserAgent()
        # profile 跨对话框存活，cookieAdded 连接需在关闭时断开（done 里处理），
        # 否则对话框析构后槽函数仍被触发会崩溃。loadAllCookies 重新触发已
        # 持久化 cookie 的 cookieAdded，确保复用 profile 时 self._cookies 也能填充。
        self._profile.cookieStore().cookieAdded.connect(self._on_cookie_added)
        self._profile.cookieStore().loadAllCookies()

        self._page = _CapturePage(self._profile, self)
        self._page.captured.connect(self._on_request_captured)
        self._page.urlChanged.connect(self._on_url_changed)

        self._build_ui()
        self._view.load(QUrl(BASE_URL))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        self._view = QWebEngineView()
        self._view.setPage(self._page)
        layout.addWidget(self._view, 1)

    def _build_header(self):
        bar = _DialogTitleBar(self)
        bar.setObjectName("titleBar")
        bar.setFixedHeight(40)

        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 8, 0)
        row.setSpacing(8)

        title = QLabel("登录选课系统")
        title.setObjectName("titleBarText")
        row.addWidget(title)

        self._status = QLabel("请完成登录，凭据捕获后窗口会自动关闭")
        self._status.setObjectName("cardHint")
        row.addWidget(self._status)
        row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("windowCloseBtn")
        close_btn.setFixedSize(36, 28)
        close_btn.clicked.connect(self.reject)
        row.addWidget(close_btn)

        return bar

    def resizeEvent(self, event):
        # 内嵌 QWebEngineView 不适合走半透明窗口方案（Chromium 合成有
        # 黑屏风险），用 mask 把无边框对话框裁成圆角。
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12.0, 12.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    # ---------- 捕获逻辑 ----------

    def _on_cookie_added(self, cookie):
        domain = cookie.domain().lstrip(".")
        # 只收集会随 jwxk.jnu.edu.cn 请求发送的 cookie（精确域或父域）
        target_host = QUrl(BASE_URL).host()
        if target_host != domain and not target_host.endswith(f".{domain}"):
            return
        name = bytes(cookie.name()).decode("utf-8", errors="ignore")
        value = bytes(cookie.value()).decode("utf-8", errors="ignore")
        self._cookies[name] = value
        self._try_finish()

    def _on_request_captured(self, data):
        if XKXF_URL.split("/")[-1] not in data.get("url", ""):
            return
        self._captured_request = data
        self.log.emit("已捕获目标请求，正在组装凭据...")
        self._try_finish()

    def _on_url_changed(self, qurl):
        # 输出导航过程，便于排查登录流程跳转到了哪个域（诊断滑块验证问题）
        host = qurl.host()
        if host:
            self.log.emit(f"页面跳转：{host}")

    def _try_finish(self):
        if self._done or not self._captured_request or not self._cookies:
            return

        cookie_header = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        headers = dict(self._captured_request.get("headers") or {})
        headers["cookie"] = cookie_header
        # JS 钩子拿不到 User-Agent（浏览器禁止脚本设置该头），补上浏览器
        # 实际使用的 UA，确保抢课请求与登录会话一致
        headers.setdefault("user-agent", self._user_agent)

        captured_data = {
            "url": self._captured_request.get("url", ""),
            "request_headers": headers,
            "request_payload": self._captured_request.get("body", ""),
            "response_body": "",
        }

        try:
            credentials = Credentials.from_capture(captured_data)
        except CredentialError as exc:
            # token 或请求体未就绪时继续等待下一次请求
            self.log.emit(f"凭据暂不完整（{exc}），继续等待...")
            return

        self._done = True
        self.log.emit("凭据捕获成功。")
        self.credentials_captured.emit(credentials)
        self.accept()

    def done(self, result):
        # accept()/reject()/close() 都会经过这里（closeEvent 在 accept/reject
        # 路径下不会触发）。profile 是进程内共享单例、不在此销毁，但必须断开
        # 本对话框对 cookieAdded 的连接，否则对话框析构后槽函数仍被触发会崩溃。
        try:
            self._profile.cookieStore().cookieAdded.disconnect(self._on_cookie_added)
        except (TypeError, RuntimeError):
            pass
        # 先排队销毁本对话框自己的 page（page 归属对话框，profile 归属 app）。
        if self._page is not None:
            self._view.setPage(None)
            self._page.deleteLater()
            self._page = None
        super().done(result)


class _DialogTitleBar(QWidget):
    """可拖动的对话框标题栏。"""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemMove()
        super().mousePressEvent(event)
