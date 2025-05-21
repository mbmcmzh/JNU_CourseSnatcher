import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
from core import JNUCourseSnatcher
import os
import json

def resource_path(relative_path):
    """
    获取资源文件的绝对路径，兼容打包和开发环境。
    - 在开发环境中，文件路径相对于当前目录。
    - 在打包后的可执行文件中，文件路径相对于临时目录（sys._MEIPASS）。
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class TextRedirector:
    """
    将 print 输出重定向到指定的 Text 控件中。
    - write 方法将文本插入到 Text 控件，并确保滚动到最新内容。
    - flush 方法不做任何处理。
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
        self.snatcher = JNUCourseSnatcher()  # 创建抢课助手实例
        self.title("暨大抢课助手 2.5")  # 设置窗口标题
        self.geometry("800x600")  # 设置窗口大小
        self.running = False  # 抢课状态，初始为 False
        self.stop_event = threading.Event()  # 停止事件，用于控制抢课线程
        self.course_list = []  # 存储添加的课程
        self.create_widgets()  # 创建 UI 控件
        self.iconbitmap(resource_path("icon.ico"))  # 设置窗口图标
        sys.stdout = TextRedirector(self.log_area)  # 重定向 print 输出到日志框

    def create_widgets(self):
        # 登录区域
        input_frame = ttk.LabelFrame(self, text="登录状态")
        input_frame.pack(padx=10, pady=5, fill=tk.X)

        self.login_btn = ttk.Button(input_frame, text="点击登录", command=self.start_login)
        self.login_btn.pack(side=tk.LEFT, padx=5)

        self.login_status = ttk.Label(input_frame, text="未登录")
        self.login_status.pack(side=tk.LEFT, padx=10)

        # 课程信息输入区域
        course_frame = ttk.LabelFrame(self, text="课程信息")
        course_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # 输入控件框架
        input_frame = ttk.Frame(course_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        # 轮次选择
        ttk.Label(input_frame, text="轮次:").grid(row=0, column=0, sticky=tk.W)
        self.elective_batch_var = tk.StringVar()
        self.elective_batch_combo = ttk.Combobox(
            input_frame,
            textvariable=self.elective_batch_var,
            values=["第一轮", "第二轮"],
            state="readonly"
        )
        self.elective_batch_combo.grid(row=0, column=1, sticky=tk.W)
        self.elective_batch_combo.current(0)  # 默认选择第一轮

        # 课程代码输入
        ttk.Label(input_frame, text="课程代码:").grid(row=0, column=2, sticky=tk.W)
        self.teaching_class_id_entry = ttk.Entry(input_frame)
        self.teaching_class_id_entry.grid(row=0, column=3, sticky=tk.W)

        # 校区选择
        ttk.Label(input_frame, text="校区:").grid(row=0, column=4, sticky=tk.W)
        self.campus_var = tk.StringVar()
        self.campus_combo = ttk.Combobox(
            input_frame,
            textvariable=self.campus_var,
            values=["本部", "番禺", "海珠"],
            state="readonly"
        )
        self.campus_combo.grid(row=0, column=5, sticky=tk.W)
        self.campus_combo.current(0)  # 默认选择本部

        # 添加课程按钮
        self.add_course_btn = ttk.Button(input_frame, text="添加课程", command=self.add_course)
        self.add_course_btn.grid(row=0, column=6, padx=5)

        # 已添加课程列表
        self.course_listbox = tk.Listbox(course_frame)
        self.course_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 移除课程按钮
        self.remove_course_btn = ttk.Button(course_frame, text="移除选中课程", command=self.remove_course)
        self.remove_course_btn.pack(side=tk.BOTTOM, pady=5)

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


    def add_course(self):
        """
        添加课程到列表。
        - 从 UI 中获取用户输入（轮次、课程代码、校区）。
        - 构造 addParam 字典。
        - 将课程信息添加到 self.course_list 并显示在 course_listbox 中。
        """
        # 检查是否已登录
        if not hasattr(self, 'student_code'):
            messagebox.showerror("错误", "请先登录")
            return

        elective_batch = self.elective_batch_var.get()
        teaching_class_id = self.teaching_class_id_entry.get().strip()
        campus = self.campus_var.get()

        if not teaching_class_id:
            messagebox.showerror("错误", "请输入课程代码")
            return

        # 映射显示值到实际的 electiveBatchCode
        batch_map = {"第一轮": "e774c64e3849470d941eb23f5e712d7b", "第二轮": "f8e5c6e0dbca44bbb0401b51b5f54490"}
        # 映射显示值到实际的 campus 代码
        campus_map = {"本部": "0", "番禺": "1", "海珠": "2"}

        batch_code = batch_map[elective_batch]
        campus_code = campus_map[campus]

        # 构造 addParam 字典
        add_param = {
            "data": {
                "operationType": "1",
                "studentCode": self.student_code,  # 从登录获取的学号
                "electiveBatchCode": batch_code,
                "teachingClassId": teaching_class_id,
                "isMajor": "1",
                "campus": campus_code,
                "teachingClassType": "QXKC",
                "chooseVolunteer": "1"
            }
        }

        # 构造课程信息字典
        course = {
            "class_data": {"addParam": json.dumps(add_param)},  # 转换为 JSON 字符串
            "display_name": f"课程ID: {teaching_class_id}, 轮次: {elective_batch}, 校区: {campus}"
        }

        # 添加到课程列表和 Listbox
        self.course_list.append(course)
        self.course_listbox.insert(tk.END, course["display_name"])
        self.teaching_class_id_entry.delete(0, tk.END)  # 清空课程代码输入框

    def remove_course(self):
        """
        移除选中的课程。
        - 从 course_listbox 和 self.course_list 中删除选中的课程。
        """
        selected = self.course_listbox.curselection()
        if selected:
            index = selected[0]
            self.course_listbox.delete(index)
            del self.course_list[index]

    def log(self, message):
        """
        将消息插入到日志框中。
        - 启用 Text 控件，插入消息，禁用 Text 控件，滚动到最新内容。
        """
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.configure(state=tk.DISABLED)
        self.log_area.see(tk.END)

    def clear_log(self):
        """
        清除日志框中的内容。
        """
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def toggle(self):
        """
        切换抢课状态。
        - 如果未在抢课，则启动抢课；否则停止抢课。
        """
        if not self.running:
            self.start_snatch()
        else:
            self.stop_snatch()

    def start_login(self):
        """
        启动登录流程。
        - 禁用登录按钮，显示“正在登录...”。
        - 在新线程中调用 get_cookie_and_token 获取学号、Cookie 和 Token。
        - 更新登录状态。
        """
        if hasattr(self, 'login_thread') and self.login_thread.is_alive():
            return  # 防止重复启动线程

        self.login_btn.config(state=tk.DISABLED)
        self.login_status.config(text="正在登录...")

        def login_task():
            try:
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
        """
        启动抢课流程。
        - 检查是否已登录和是否已添加课程。
        - 设置抢课状态，启动抢课线程。
        """
        if not hasattr(self, 'student_code') or not self.student_code:
            messagebox.showerror("错误", "请先点击登录按钮登录系统")
            return

        if not self.course_list:
            messagebox.showerror("错误", "请先添加课程")
            return

        self.running = True
        self.stop_event.clear()
        self.start_btn.config(text="停止抢课")

        threading.Thread(
            target=self.snatcher.start_snatching,
            args=(self.headers, self.course_list, self.log, self.stop_event),
            daemon=True
        ).start()

    def stop_snatch(self):
        """
        停止抢课流程。
        - 设置停止事件，更新按钮文本，记录日志。
        """
        self.running = False
        self.stop_event.set()
        self.start_btn.config(text="开始抢课")
        self.log("抢课已停止")


if __name__ == "__main__":
    app = CourseSnatcherUI()
    app.mainloop()