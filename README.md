# 暨南大学抢课助手

一个基于 Python 的暨南大学抢课脚本，支持图形界面和命令行两种使用方式。

## 功能特点

- 🚀 **自动抢课**：自动监听网络请求，获取登录信息后批量抢课
- 💻 **图形界面**：提供友好的 GUI 界面，操作简单直观
- 🔄 **多轮抢课**：支持设置多轮抢课，提高成功率
- 🌐 **内置浏览器**：包含 Chrome 浏览器，无需额外安装
- 📝 **详细日志**：显示抢课过程和结果，便于调试

## 下载和使用

### 完整版本下载

由于包含浏览器文件较大，完整版本请从 [Releases](https://github.com/mbmcmzh/JNU_CourseSnatcher/releases) 页面下载：

1. 访问 [Releases 页面](https://github.com/mbmcmzh/JNU_CourseSnatcher/releases)
2. 下载 `JNU_CourseSnatcher_Complete.zip`
3. 解压到本地目录
4. 运行程序

### 源码版本

如果你只需要源码，可以直接克隆此仓库：

```bash
git clone https://github.com/mbmcmzh/JNU_CourseSnatcher.git
```

注意：源码版本需要自行安装 Chrome 浏览器。

## 运行要求

- Python 3.7+
- Chrome 浏览器（完整版本已包含）
- 网络连接

## 使用方法
注意！添加课程请输入班号，而不要输入课程号！


### 图形界面版本
```bash
python gui.py
```

### 命令行版本
```bash
python main.py
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 注意事项

- 请合理使用，遵守学校相关规定
- 建议在选课时间段使用，避免对服务器造成压力
- 使用前请确保网络连接稳定

## 免责声明

本工具仅供学习交流使用，请遵守学校相关规定，作者不承担任何责任。 
