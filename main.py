import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
from core import JNUCourseSnatcher
import os
from tkinter import PhotoImage

def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容打包和开发环境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class TextRedirector:
    """
    将 print 输出重定向到指定的 Text 控件中
    """
    def __init__(self, widget):
        self.widget = widget

    def write(self, s):
        if s.strip():  # 避免空行也写入
            # 因为可能在其他线程中调用，所以用 after 来调度更新
            self.widget.after(0, self._append_text, s)

    def _append_text(self, s):
        self.widget.configure(state=tk.NORMAL)
        self.widget.insert(tk.END, s)
        self.widget.configure(state=tk.DISABLED)
        self.widget.see(tk.END)

    def flush(self):
        pass  # 不做任何处理

class CourseSnatcherUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.snatcher = JNUCourseSnatcher()
        self.title("暨大抢课助手 2.0")
        self.geometry("800x600")
        self.running = False
        self.stop_event = threading.Event()
        self.create_widgets()
        self.iconbitmap(resource_path("icon.ico"))

        # 将 sys.stdout 重定向到日志框
        sys.stdout = TextRedirector(self.log_area)

    def create_widgets(self):
        # 修改后的输入区域
        input_frame = ttk.LabelFrame(self, text="登录状态")
        input_frame.pack(padx=10, pady=5, fill=tk.X)

        self.login_btn = ttk.Button(input_frame, text="点击登录", command=self.start_login)
        self.login_btn.pack(side=tk.LEFT, padx=5)

        self.login_status = ttk.Label(input_frame, text="未登录")
        self.login_status.pack(side=tk.LEFT, padx=10)

        # 课程输入区域
        course_frame = ttk.LabelFrame(self, text="课程信息（每行一个课程）")
        course_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.course_input = tk.Text(course_frame, height=10)
        scroll = ttk.Scrollbar(course_frame, command=self.course_input.yview)
        self.course_input.configure(yscrollcommand=scroll.set)
        self.course_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 设置示例文本作为占位符
        self.placeholder = """addParam: {"data":{"operationType":"1","studentCode":"学号","electiveBatchCode":"一串32位的字符","teachingClassId":"课程代码","isMajor":"1","campus":"校区编号","teachingClassType":"选课类型","chooseVolunteer":"1"}}"""
        self._add_placeholder()  # 初始时添加占位符
        # 绑定焦点事件，用于显示/清除占位符
        self.course_input.bind("<FocusIn>", self._clear_placeholder)
        self.course_input.bind("<FocusOut>", self._add_placeholder)

        # 控制按钮区域
        btn_frame = ttk.Frame(self)
        btn_frame.pack(padx=10, pady=5, fill=tk.X)

        self.start_btn = ttk.Button(btn_frame, text="开始抢课", command=self.toggle)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="清除日志", command=self.clear_log).pack(side=tk.RIGHT, padx=5)

        # 日志区域
        log_frame = ttk.LabelFrame(self, text="运行日志")
        log_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.log_area = tk.Text(log_frame, state=tk.DISABLED)
        scroll_log = ttk.Scrollbar(log_frame, command=self.log_area.yview)
        self.log_area.configure(yscrollcommand=scroll_log.set)
        self.log_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_log.pack(side=tk.RIGHT, fill=tk.Y)

    def _clear_placeholder(self, event):
        current = self.course_input.get("1.0", tk.END).strip()
        if current == self.placeholder:
            self.course_input.delete("1.0", tk.END)
            self.course_input.config(fg="black")

    def _add_placeholder(self, event=None):
        current = self.course_input.get("1.0", tk.END).strip()
        if not current:
            self.course_input.insert("1.0", self.placeholder)
            self.course_input.config(fg="grey")

    def log(self, message):
        # 虽然 print 已经重定向，但 UI 内部日志写入仍然可以调用此方法
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.configure(state=tk.DISABLED)
        self.log_area.see(tk.END)

    def clear_log(self):
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def toggle(self):
        if not self.running:
            self.start_snatch()
        else:
            self.stop_snatch()

    def start_login(self):
        if hasattr(self, 'login_thread') and self.login_thread.is_alive():
            return

        self.login_btn.config(state=tk.DISABLED)
        self.login_status.config(text="正在登录...")
        
        def login_task():
            try:
                # 获取凭证并自动设置学号
                self.headers = self.snatcher.get_cookie_and_token()
                self.student_code = self.headers['student_code']
                self.login_status.config(text=f"已登录: {self.student_code}")
                self.login_btn.config(state=tk.NORMAL)
            except Exception as e:
                self.log(f"登录失败: {str(e)}")
                self.login_status.config(text="登录失败")
                self.login_btn.config(state=tk.NORMAL)

        self.login_thread = threading.Thread(target=login_task, daemon=True)
        self.login_thread.start()

    def start_snatch(self):
        if not hasattr(self, 'student_code') or not self.student_code:
            messagebox.showerror("错误", "请先点击登录按钮登录系统")
            return

        course_data = self.course_input.get(1.0, tk.END).strip()
        if course_data == self.placeholder:
            course_data = ""

        try:
            course_list = self.snatcher.parse_course_data(course_data)
            self.running = True
            self.stop_event.clear()
            self.start_btn.config(text="停止抢课")

            threading.Thread(
                target=self.snatcher.start_snatching,
                args=(self.headers, course_list, self.log, self.stop_event),
                daemon=True
            ).start()
        except Exception as e:
            self.log(f"初始化失败: {str(e)}")
            self.stop_snatch()

    def stop_snatch(self):
        self.running = False
        self.stop_event.set()
        self.start_btn.config(text="开始抢课")
        self.log("抢课已停止")


if __name__ == "__main__":
    app = CourseSnatcherUI()
    app.mainloop()
