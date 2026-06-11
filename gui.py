"""暨南大学抢课助手 —— 图形界面入口。"""

import os
import sys

# 以下 Chromium 启动参数必须在 QtWebEngine 初始化前设置。
_chromium_flags = []

# 【关键修复】QtWebEngine(Chromium) 默认走系统(WinINet)代理。若本机开了
# Clash / V2Ray 等代理，校园门户 jnu.edu.cn 与网易易盾 126.net/163.com 的请求
# 会被路由到境外/异常节点，TLS 握手被重置(net_error -100)：轻则验证码加载不出，
# 重则拖动后的打分请求出口 IP 异常 → 滑块"对准也未通过、偶尔能过"。本应用只
# 访问校内站点，强制内嵌浏览器直连：既修复加载，又让易盾看到稳定的真实 IP。
# 确需经系统代理访问校内系统者，可设环境变量 JNU_SNATCHER_USE_PROXY=1 关闭本项。
if os.environ.get("JNU_SNATCHER_USE_PROXY") != "1":
    _chromium_flags.append("--no-proxy-server")

# 打包分发到任意电脑时，目标机可能无独显 / 在虚拟机或远程桌面里，
# GPU 初始化失败会让内嵌浏览器黑屏或崩溃。冻结环境下强制软件渲染，
# 牺牲一点性能换取"各种环境都能跑"。
if getattr(sys, "frozen", False):
    _chromium_flags.append("--disable-gpu")

if _chromium_flags:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + " " + " ".join(_chromium_flags)
    ).strip()

from PyQt6.QtWidgets import QApplication

from jnu_snatcher.gui.main_window import MainWindow
from jnu_snatcher.gui.theme import STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
