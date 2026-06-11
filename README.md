# 暨南大学抢课助手

在暨大选课系统抢课用的小工具。在程序内置的浏览器里登录一次选课系统，登录凭据
（cookie / token / 学号 / 选课批次）会被自动抓下来，之后程序按你填的教学班号
一轮一轮地提交选课请求，比手点快得多，也不用一直盯着刷新。

界面用 PyQt6 写的，另外保留了一个命令行版本。

先说一个最容易踩的坑：**添加课程时填的是「班号」（教学班号），不是课程号**。
这俩长得很像，填错了会一直查不到课。

## 怎么获取

分三种情况：

- **只是想用**：去 [Releases](https://github.com/mbmcmzh/JNU_CourseSnatcher/releases)
  下载打包好的 `JNU_CourseSnatcher.exe`，双击就能跑。不用装 Python，也不用装
  Chrome，浏览器已经内置在 exe 里了。需要 64 位 Windows 10 及以上。
- **想看 / 改代码**：直接 clone 本仓库。注意仓库是**不含 Chrome 的版本**——
  备用登录方案用的外置 Chrome 有几百 MB，传 GitHub 不现实，所以没放进来。
  主力的内嵌浏览器方案不受影响，clone 下来装好依赖就能用。
- **想要完整项目**：Releases 里另有打包的完整项目源码
  `JNU_CourseSnatcher_Complete.zip`，比仓库多了 `chrome/` 和 `chromedriver.exe`，
  备用的外置 Chrome 登录方案开箱即用。

## 从源码运行

需要 Windows、Python 3.9 以上：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python gui.py
```

流程就三步：

1. 点「登录选课系统」，在弹出的内嵌浏览器里正常登录，中间会有网易易盾的滑块验证码；
2. 登录成功后程序自动拿到凭据，浏览器窗口自己关掉；
3. 添加班号、设好轮数，开始抢课，过程和结果都在右边的日志里。

命令行版是 `python main.py`。注意它走的是外置 Chrome 嗅探方案，需要完整版里的
`chrome/` 和 `chromedriver.exe`。

### 备用登录方案是怎么回事

正常情况下用内嵌浏览器登录就够了。如果哪天内嵌浏览器出问题（比如 Qt 升级后
指纹又对不上了），界面上还留了一个「备用：外置 Chrome 登录」按钮，原理是用
selenium-wire 起一个真正的 Chrome、嗅探请求把凭据抓下来。这个方案依赖
`chrome/` 文件夹和 `chromedriver.exe`，仓库里没有，在 Releases 的完整包里。

### 自己打包 exe

```bash
pip install pyinstaller
pyinstaller JNU_CourseSnatcher.spec --noconfirm --clean
```

产物是 `dist/JNU_CourseSnatcher.exe`。单文件，只含内嵌浏览器方案——selenium
那套在 spec 里被排除了，Chrome 更不会被打进去。打包版启动时会自动加
`--disable-gpu`，没独显的电脑、虚拟机、远程桌面里也能正常显示。

两点说明：

- 单文件 exe 启动时要先解压到临时目录，第一次打开慢几秒是正常的；
- exe 没有数字签名，SmartScreen 或者杀软可能会拦一下，属于误报。介意的话
  直接 clone 源码自己打包就好。

## 滑块验证码那个坑（排查记录）

这是这个项目踩过的最大的坑，记录在这里，省得以后再掉进去。

### 现象

用内嵌浏览器登录统一身份认证（icas.jnu.edu.cn）时，网易易盾的滑块拼图
**对得再准也提示"未通过"**，十几次里偶尔才能过一次。但同一台电脑上用真正的
Chrome 登录，基本一次就过。

### 排查过程

一开始怀疑是 Windows 125% 缩放导致 Qt/Chromium 坐标错位，滑块"看着对准了
实际没对准"。实测了 4 种 DPI 模式：网页 DPR 和 Qt DPR 全部一致、拖动时红点
完全贴合、位移比值正好 1.000——几何因素是清白的，这条路排除（当时为此加的
取整改动也回退了）。

然后写了一个只调易盾、不碰学校登录的本地 demo 页反复试，对比内嵌浏览器和
真实 Chrome 的指纹，发现关键差异在**浏览器语言**上：QtWebEngine 默认
`navigator.languages = ["en"]`，而同一台机器上的 Chrome 是 `zh-CN`。
一个声称自己是纯英文环境的浏览器，挂着国内 IP、操着中文时区、访问国内高校
站点——在中文风控引擎眼里这就是个异常环境。把语言改成中文后，滑块立刻就能过了。

### 修复

决定性的一行在 `jnu_snatcher/gui/embedded_browser.py`，把 Accept-Language
和页面里的 `navigator.languages` 一起对齐成中文：

```python
profile.setHttpAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.8")
```

另外还有一个独立的问题：本机开着 Clash 这类代理时，QtWebEngine 会跟着系统
代理走，校园网和易盾（126.net / 163.com）的请求可能被路由到境外节点，国内
站点直接把连接 RST 掉，表现为验证码脚本压根加载不出来（net_error -100）。
所以 `gui.py` 里让内嵌浏览器强制直连（反正它只访问校内站点）：

```python
if os.environ.get("JNU_SNATCHER_USE_PROXY") != "1":
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] += " --no-proxy-server"
```

要强调的是：直连只解决"验证码能不能加载出来"，**解决不了"对准也不过"**——
当时设了直连之后滑块照样不过，直到把语言改成中文才通过。所以这两个修复
是叠加关系，语言对齐才是决定性的那个。确实需要走代理访问校内系统的话，
设环境变量 `JNU_SNATCHER_USE_PROXY=1` 可以恢复走系统代理。

### 顺手做的加固

这些不是决定性因素，但都能降低风控分，已经一并改进去了：

- 登录用 off-the-record（不落盘）会话：cookie / 缓存 / localStorage 都只在内存里，
  窗口一关就清空，每次打开都是干净的全新状态，不残留上次的登录信息。
  （早期试过把 profile 持久化来"攒设备信誉"，但既然语言对齐就解决了问题，
  就改回每次全新，更干净也更省心。）
- 给 `navigator.userAgentData` 的品牌列表补上真实 Chrome 才有的
  `Google Chrome` 项（读改写，保留 Qt 原有的 GREASE 品牌，避免越伪装破绽越多）。
- UA 里去掉 `QtWebEngine/x.y.z` 字样，并把登录时捕获的真实 UA 透传给后续
  抢课请求，保证会话前后一致。
- XHR/fetch 捕获钩子只注入选课域 `jwxk.jnu.edu.cn`，认证页和滑块页保持原生，
  免得风控用 `toString()` 之类的手段发现原型被改过。

修完之后内嵌浏览器的滑块通过率和真实 Chrome 基本没差别了（demo 页之前
12 次只过 1 次，修完稳定通过）。

## 项目结构

```
gui.py                          图形界面入口（Chromium 启动参数在这里设）
main.py                         命令行入口（走外置 Chrome 方案）
JNU_CourseSnatcher.spec         PyInstaller 打包配置
jnu_snatcher/
  config.py                     URL、默认参数、持久化目录
  credentials.py                凭据解析（cookie / token / 学号 / 批次）
  api.py                        选课系统接口（查课 / 抢课）
  sniffer.py                    selenium-wire 外置浏览器嗅探（备用登录）
  gui/
    main_window.py              主窗口与抢课流程
    embedded_browser.py         内嵌浏览器登录 + 凭据捕获（含上面那些风控修复）
    workers.py                  后台线程任务
    theme.py                    界面样式
tests/                          单元测试（pip install -r requirements-dev.txt 后 pytest）
```

## 提醒

- 再说一遍：填**班号**，不是课程号。
- 轮数别设得太夸张，请求之间本来就留了间隔，给教务系统留条活路。
- 仅供学习交流，请遵守学校的选课规定，用这个工具产生的任何后果自负。
