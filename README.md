# 暨南大学抢课助手

（用Fable 5 来重构这个是不是有点大炮打蚊子了）
在抢课开始前在程序自带的浏览器里登录一次，cookie、token、学号、选课批次会被自动抓下来，然后你把想要的课填进去，到时间点开抢就好了，因为不用加载页面所以很快。

**添加课程时填的是「教学班号」，不是课程号。**


## 使用教程
1. **抢课开始前 5~8 分钟**，趁教务系统还没被挤崩，点「登录选课系统」，在弹出来的浏览器里正常登录。
2. 登录成功后程序自动拿到凭据，浏览器窗口会自己关掉。
3. 把要抢的**教学班号**加进去。
4. 课加完就等着别乱点，也不要再去教务登录了，不然会把登录状态覆盖掉，等到10点直接点开抢就好了

## 下载

已经打包了一个exe，直接在 [Releases](https://github.com/mbmcmzh/JNU_CourseSnatcher/releases) 下 `JNU_CourseSnatcher.exe`就好

注意 exe 没签名，可能会被拦截，而且打包的是单文件，第一次启动要先解压到临时目录，可能会卡几秒。

## 源码部署

Python 3.9 以上：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python gui.py
```





## 重构过程遇到的一个问题，可能有启发（下面是ai写的，比较入机）

内嵌浏览器早期有个怪毛病：滑块对得再准也提示"未通过"，但同一台机器上的真实 Chrome 一次就过。查到最后发现根因在浏览器语言——QtWebEngine 默认报 `navigator.languages = ["en"]`，可机器是国内 IP、中文时区、访问的又是国内高校站点，挂个纯英文环境在中文风控眼里就是异常。把语言对齐成 `zh-CN`（`embedded_browser.py` 里的 `setHttpAcceptLanguage`）之后，滑块立刻就正常了。

另外一个独立的坑：本机开着 Clash 之类的代理时，QtWebEngine 会跟着系统代理走，校内站点和易盾的请求被路由到境外节点直接 RST，表现是验证码脚本压根加载不出来。所以程序默认让内嵌浏览器直连（反正只访问校内站点）。确实要走代理的话，设环境变量 `JNU_SNATCHER_USE_PROXY=1` 即可恢复。

## 项目结构

```
gui.py                  图形界面入口（Chromium 启动参数在这里设）
main.py                 命令行入口（外置 Chrome 方案）
JNU_CourseSnatcher.spec PyInstaller 打包配置
jnu_snatcher/
  config.py             URL、默认参数
  credentials.py        凭据解析（cookie / token / 学号 / 批次）
  api.py                选课系统接口（查课 / 抢课）
  sniffer.py            selenium-wire 外置浏览器嗅探（备用登录）
  gui/                  主窗口、内嵌浏览器登录、后台线程、样式
tests/                  单元测试
```

## 最后

仅供学习交流，请遵守学校的选课规定，用本工具产生的任何后果自负。
