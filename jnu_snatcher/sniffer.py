"""基于 selenium-wire 的登录请求嗅探器。"""

import atexit
import json
import os
import shutil
import sys
import tempfile
import time

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _load_webdriver():
    """惰性导入 selenium-wire，避免未安装时影响其他模块使用。"""
    import warnings

    # selenium-wire 内部使用已废弃的 pkg_resources，屏蔽其无害警告
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
    try:
        from seleniumwire import webdriver
    except ImportError as exc:
        raise BrowserStartupError(
            f"selenium-wire 不可用（{exc}）。请先执行 pip install -r requirements.txt；"
            "若已安装仍报错，多为依赖版本冲突，可重新安装后重试。"
        ) from exc
    return webdriver


def _resolve_base_path():
    """定位资源根目录（兼容 PyInstaller 打包环境）。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BrowserStartupError(Exception):
    """浏览器未安装或启动失败。"""


class RequestSniffer:
    """启动浏览器并捕获指定地址的请求/响应数据。

    log 参数接受一个 callable(str)，用于把过程信息输出到
    控制台（CLI）或日志面板（GUI）。
    """

    def __init__(self, log=print):
        self.log = log

    def _create_temp_profile(self):
        """为本次会话创建唯一的浏览器用户数据目录，退出时自动清理。"""
        temp_dir = os.path.join(
            tempfile.gettempdir(), f"jnu_sniffer_chrome_{os.getpid()}_{int(time.time())}"
        )
        shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        def _cleanup():
            shutil.rmtree(temp_dir, ignore_errors=True)

        atexit.register(_cleanup)
        return temp_dir

    def _build_chrome_options(self, webdriver, temp_dir):
        chrome_options = webdriver.ChromeOptions()

        # 优先使用程序目录下的内置浏览器 chrome/chrome.exe
        chrome_exe_path = os.path.join(_resolve_base_path(), "chrome", "chrome.exe")
        if os.path.exists(chrome_exe_path):
            self.log(f"已找到内置浏览器: {chrome_exe_path}")
            chrome_options.binary_location = chrome_exe_path
        else:
            self.log("未找到内置浏览器，将使用系统已安装的 Chrome。")

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        for arg in (
            "--disable-extensions",
            "--disable-blink-features=AutomationControlled",
            "--ignore-certificate-errors",
            "--ignore-ssl-errors",
            "--allow-running-insecure-content",
            "--disable-web-security",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-features=VizDisplayCompositor",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-networking",
            f"--user-data-dir={temp_dir}",
            f"--disk-cache-dir={temp_dir}/cache",
            "--no-first-run",
            "--no-default-browser-check",
        ):
            chrome_options.add_argument(arg)

        return chrome_options

    def _build_service(self):
        """优先使用程序目录下与内置浏览器配套的 chromedriver.exe。"""
        driver_path = os.path.join(_resolve_base_path(), "chromedriver.exe")
        if os.path.exists(driver_path):
            from selenium.webdriver.chrome.service import Service

            self.log(f"已找到本地驱动: {driver_path}")
            return Service(executable_path=driver_path)
        self.log("未找到本地 chromedriver.exe，将由 Selenium 自动匹配驱动（需要网络）。")
        return None

    def _init_browser(self):
        webdriver = _load_webdriver()
        temp_dir = self._create_temp_profile()
        seleniumwire_options = {
            "disable_encoding": True,
            "verify_ssl": False,
            "suppress_connection_errors": True,
            "disable_capture": False,
        }

        try:
            self.log("正在启动浏览器...")
            kwargs = {
                "options": self._build_chrome_options(webdriver, temp_dir),
                "seleniumwire_options": seleniumwire_options,
            }
            service = self._build_service()
            if service is not None:
                kwargs["service"] = service
            return webdriver.Chrome(**kwargs)
        except Exception as exc:
            self.log(f"浏览器启动失败: {exc}")
            raise BrowserStartupError(
                "未检测到可用浏览器。请安装谷歌浏览器（https://www.google.com/chrome/）"
                "或将内置浏览器放在程序根目录的 chrome/chrome.exe 后重试。"
            ) from exc

    @staticmethod
    def _decode_body(body):
        """请求/响应体按 JSON 美化，失败则按纯文本返回。"""
        if not body:
            return "无"
        try:
            return json.dumps(json.loads(body.decode("utf-8")), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return body.decode("utf-8", errors="ignore")

    def sniff_requests(self, visit_url, target_url, timeout=60, should_stop=None):
        """打开 visit_url，在 timeout 秒内捕获包含 target_url 的请求。

        返回包含 url / request_headers / request_payload / response_body
        的字典；超时或被 should_stop() 中断时返回 None。
        """
        driver = self._init_browser()
        self.log(f"浏览器已启动，正在访问: {visit_url}")
        driver.get(visit_url)

        self.log("请在浏览器中完成登录以触发目标请求。")
        self.log(f"正在监听目标地址: {target_url}（最长等待 {timeout} 秒）")

        deadline = time.time() + timeout
        captured_data = None

        try:
            while time.time() < deadline:
                if should_stop and should_stop():
                    self.log("嗅探已被手动停止。")
                    break

                for request in driver.requests:
                    if request.response and target_url in request.url:
                        self.log(f"捕获到目标请求: {request.url}")
                        headers = {
                            str(k).lower(): v for k, v in dict(request.headers).items()
                        }
                        payload_str = "无"
                        if request.body:
                            payload_str = request.body.decode("utf-8", errors="ignore")

                        captured_data = {
                            "url": request.url,
                            "request_headers": headers,
                            "request_payload": payload_str,
                            "response_body": self._decode_body(request.response.body),
                        }
                        del driver.requests
                        break

                if captured_data:
                    break
                time.sleep(1)

            if not captured_data and not (should_stop and should_stop()):
                self.log(f"在 {timeout} 秒内未捕获到目标地址的请求。")
        finally:
            self.log("正在关闭浏览器...")
            driver.quit()

        return captured_data
