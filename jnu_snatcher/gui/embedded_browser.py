"""内嵌浏览器登录窗口。

基于 QWebEngineView 直接在应用内完成登录：
- 通过注入 JS 钩住 XMLHttpRequest / fetch，捕获 xkxf.do 请求的
  token 请求头与请求体（xh / xklcdm）；
- 通过 QWebEngineProfile 的 CookieStore 收集站点 Cookie；
- 两者凑齐后组装成与 selenium-wire 嗅探器相同格式的捕获数据。
"""

import json

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import BASE_URL, XKXF_URL
from ..credentials import CredentialError, Credentials

_CAPTURE_PREFIX = "JNU_CAPTURE:"

# 钩住 XHR 与 fetch，命中目标接口时把请求头与请求体打到 console
_HOOK_SCRIPT = """
(function() {
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


class EmbeddedLoginDialog(QDialog):
    """内嵌浏览器登录对话框。

    捕获到完整凭据后发出 credentials_captured 并自动关闭。
    """

    credentials_captured = pyqtSignal(object)
    log = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录选课系统")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.resize(1080, 760)
        self.setModal(True)

        self._cookies = {}
        self._captured_request = None
        self._done = False

        # 独立的临时 profile（不落盘，每次启动都是干净会话）
        self._profile = QWebEngineProfile(self)
        self._profile.cookieStore().cookieAdded.connect(self._on_cookie_added)

        script = QWebEngineScript()
        script.setName("jnu-capture-hook")
        script.setSourceCode(_HOOK_SCRIPT)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)
        self._profile.scripts().insert(script)

        self._page = _CapturePage(self._profile, self)
        self._page.captured.connect(self._on_request_captured)

        self._build_ui()
        self._view.load(QUrl(BASE_URL))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
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

    def _try_finish(self):
        if self._done or not self._captured_request or not self._cookies:
            return

        cookie_header = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        headers = dict(self._captured_request.get("headers") or {})
        headers["cookie"] = cookie_header

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

    def closeEvent(self, event):
        # 先解除并销毁 page，避免 profile 先于 page 析构导致崩溃
        self._view.setPage(None)
        self._page.deleteLater()
        super().closeEvent(event)


class _DialogTitleBar(QWidget):
    """可拖动的对话框标题栏。"""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemMove()
        super().mousePressEvent(event)
