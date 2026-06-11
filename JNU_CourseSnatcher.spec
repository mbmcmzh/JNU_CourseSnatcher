# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：暨南大学抢课助手（内嵌浏览器版 · 单文件 exe）。

用法：
    pyinstaller JNU_CourseSnatcher.spec --noconfirm --clean

产物：
    dist/JNU_CourseSnatcher.exe
    单文件、自包含 Qt6 + Chromium 运行时，目标机无需安装 Python / Qt / Chrome。

说明：
    - QtWebEngine 的进程、ICU 数据、locales、*.pak 等资源由 PyInstaller
      自带的 PyQt6 hook 自动收集，无需手工指定。
    - 内嵌浏览器版用不到 selenium / selenium-wire（外置 Chrome 备用方案），
      在 excludes 中排除以缩小体积；打包版点击"备用：外置 Chrome 登录"
      会得到友好提示而非崩溃（sniffer 对缺失依赖已做兜底）。
"""

block_cipher = None

# 内嵌浏览器相关子模块，部分为条件 import，显式声明以防漏收集
hiddenimports = [
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebChannel",
    "PyQt6.QtNetwork",
    "PyQt6.QtPrintSupport",
]

# 内嵌浏览器版用不到的重型 / 无关依赖：缩小体积、降低杀软误报概率
excludes = [
    "selenium",
    "seleniumwire",
    "PyQt5",
    "PySide2",
    "PySide6",
    "tkinter",
    "pytest",
    "IPython",
    "jupyter",
    "notebook",
    "matplotlib",
    "scipy",
    "pandas",
]

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="JNU_CourseSnatcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # WebEngine 的 DLL 经 UPX 压缩易损坏，且更易触发杀软误报
    runtime_tmpdir=None,
    console=False,        # GUI 程序：不显示控制台黑窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
