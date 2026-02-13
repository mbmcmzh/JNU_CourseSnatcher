import sys
import time
import json
from urllib.parse import parse_qs
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTextEdit, QLineEdit, QLabel, QListWidget, 
    QSpinBox, QMessageBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QIcon

# 从主脚本导入核心逻辑
# 确保两个脚本位于同一目录下
try:
    from main import RequestSniffer, course_search, course_addParam_generate, course_snatch, BASE_URL, get_header_case_insensitive
except ImportError:
    print("错误: 无法从 main.py 导入模块。请确保 main.py 和 gui.py 在同一个目录下。")
    sys.exit(1)

# --- 后台工作线程定义 ---

class Stream(QObject):
    """用于重定向标准输出流的对象"""
    newText = pyqtSignal(str)

    def write(self, text):
        self.newText.emit(str(text))
    
    def flush(self):
        pass

class SnifferWorker(QObject):
    """负责执行网络嗅探任务的工作对象"""
    finished = pyqtSignal()
    log = pyqtSignal(str)
    data_captured = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, browser_wait_time):
        super().__init__()
        self.browser_wait_time = browser_wait_time

    @pyqtSlot()
    def run(self):
        try:
            self.log.emit("开始启动浏览器嗅探器...")
            self.log.emit(f"请在 {self.browser_wait_time} 秒内完成登录操作...")
            xkxf_URL = f"{BASE_URL}xsxkapp/sys/xsxkapp/student/xkxf.do"
            sniffer = RequestSniffer()
            captured_data = sniffer.sniff_requests(
                visit_url=BASE_URL,
                target_url=xkxf_URL,
                timeout=self.browser_wait_time
            )
            if captured_data:
                self.log.emit("--- 成功捕获到请求信息！---")
                self.data_captured.emit(captured_data)
            else:
                self.error.emit(f"在 {self.browser_wait_time} 秒内未捕获到目标URL的请求。")
        except Exception as e:
            self.error.emit(f"嗅探过程中发生严重错误: {e}")
        finally:
            self.finished.emit()

class SnatcherWorker(QObject):
    """负责执行抢课任务的工作对象"""
    finished = pyqtSignal()
    log = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, headers, student_code, electiveBatchCode, course_classid_list, repeat_snatch_time):
        super().__init__()
        self.headers = headers
        self.student_code = student_code
        self.electiveBatchCode = electiveBatchCode
        self.course_classid_list = course_classid_list
        self.repeat_snatch_time = repeat_snatch_time
        self._is_running = True

    @pyqtSlot()
    def stop(self):
        self._is_running = False
        self.log.emit("抢课任务已手动停止。")

    @pyqtSlot()
    def run(self):
        try:
            self.log.emit("1. 开始获取课程详细信息...")
            course_info_list = []
            for queryContent in self.course_classid_list:
                if not self._is_running: return
                self.log.emit(f"正在查询班号: {queryContent}")
                course_info = course_search(self.headers, self.student_code, self.electiveBatchCode, queryContent)
                
                if course_info and course_info.get('dataList'):
                    if course_info['dataList']:
                        course_info_list.append(course_info)
                        self.log.emit(f"✅ 成功获取班号 {queryContent} 的信息。")
                    else:
                        msg = course_info.get('msg', '无具体错误信息')
                        self.error.emit(f"❌ 查询班号 {queryContent} 失败: {msg}")
                else:
                    self.error.emit(f"❌ 查询班号 {queryContent} 失败，响应为空或格式不正确。")
            
            if not course_info_list:
                self.error.emit("未能获取任何有效的课程信息，抢课中止。")
                return

            self.log.emit("\n2. 生成抢课所需的提交参数...")
            addParam_list = course_addParam_generate(course_info_list, self.student_code, self.electiveBatchCode)
            
            if not addParam_list:
                self.error.emit("未能生成抢课参数，抢课中止。")
                return
            
            self.log.emit("✅ 参数生成完毕。")
            self.log.emit("\n3. 开始执行抢课循环...")
            
            for i in range(self.repeat_snatch_time):
                if not self._is_running: return
                self.log.emit(f"\n--- 🚀 第 {i+1}/{self.repeat_snatch_time} 轮抢课开始 ---")
                course_snatch(self.headers, addParam_list)
                self.log.emit(f"--- ✅ 第 {i+1}/{self.repeat_snatch_time} 轮抢课请求已发送 ---")
                if self._is_running and i < self.repeat_snatch_time - 1:
                    time.sleep(1) 
            
            if self._is_running:
                self.log.emit("\n🎉 所有抢课轮次已完成！")

        except Exception as e:
            self.error.emit(f"抢课过程中发生严重错误: {e}")
        finally:
            self.finished.emit()

# --- 主窗口界面 ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("暨南大学课程辅助脚本")
        self.setGeometry(100, 100, 800, 600)

        # 初始化数据
        self.captured_data = None
        self.headers = None
        self.student_code = None
        self.electiveBatchCode = None
        self.sniffer_thread = None
        self.sniffer_worker = None
        self.snatcher_thread = None
        self.snatcher_worker = None

        self._init_ui()
        self._redirect_stdout()

    def _init_ui(self):
        # --- 主布局 ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- 左侧控制面板 ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        main_layout.addWidget(left_panel, 1)

        # 1. 参数设置
        settings_group = QGroupBox("参数设置")
        settings_layout = QFormLayout(settings_group)
        self.repeat_snatch_spinbox = QSpinBox()
        self.repeat_snatch_spinbox.setRange(1, 100)
        self.repeat_snatch_spinbox.setValue(3)
        self.browser_wait_spinbox = QSpinBox()
        self.browser_wait_spinbox.setRange(30, 600)
        self.browser_wait_spinbox.setValue(120)
        settings_layout.addRow("抢课轮数:", self.repeat_snatch_spinbox)
        settings_layout.addRow("登录等待时间(秒):", self.browser_wait_spinbox)
        left_layout.addWidget(settings_group)
        
        # 2. 登录与凭据
        login_group = QGroupBox("第一步: 登录并获取凭据")
        login_layout = QVBoxLayout(login_group)
        self.start_sniffing_btn = QPushButton("启动浏览器进行登录")
        self.start_sniffing_btn.clicked.connect(self.start_sniffing)
        login_layout.addWidget(self.start_sniffing_btn)
        left_layout.addWidget(login_group)

        # 3. 课程班号
        courses_group = QGroupBox("第二步: 添加课程班号")
        courses_layout = QVBoxLayout(courses_group)
        self.course_id_input = QLineEdit()
        self.course_id_input.setPlaceholderText("在此输入单个教学班号后按回车或点击按钮")
        self.course_id_input.returnPressed.connect(self.add_course)
        self.add_course_btn = QPushButton("添加班号到列表")
        self.add_course_btn.clicked.connect(self.add_course)
        self.course_list_widget = QListWidget()
        self.remove_course_btn = QPushButton("从列表删除选中项")
        self.remove_course_btn.clicked.connect(self.remove_course)
        
        courses_layout.addWidget(self.course_id_input)
        courses_layout.addWidget(self.add_course_btn)
        courses_layout.addWidget(QLabel("待抢课程列表:"))
        courses_layout.addWidget(self.course_list_widget)
        courses_layout.addWidget(self.remove_course_btn)
        left_layout.addWidget(courses_group)

        # 4. 执行抢课
        snatch_group = QGroupBox("第三步: 开始执行")
        snatch_layout = QVBoxLayout(snatch_group)
        self.start_snatching_btn = QPushButton("开始抢课")
        self.start_snatching_btn.clicked.connect(self.start_snatching)
        self.stop_snatching_btn = QPushButton("停止抢课")
        self.stop_snatching_btn.clicked.connect(self.stop_snatching)
        snatch_layout.addWidget(self.start_snatching_btn)
        snatch_layout.addWidget(self.stop_snatching_btn)
        left_layout.addWidget(snatch_group)
        
        left_layout.addStretch()

        # --- 右侧日志面板 ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel, 2)
        
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_browser = QTextEdit()
        self.log_browser.setReadOnly(True)
        log_layout.addWidget(self.log_browser)
        right_layout.addWidget(log_group)

        # --- 初始状态 ---
        self.set_ui_state('initial')

    def _redirect_stdout(self):
        """将打印输出重定向到日志窗口"""
        sys.stdout = Stream(newText=self.update_log)
        sys.stderr = Stream(newText=self.update_log)
        print("界面初始化完成。")

    def set_ui_state(self, state):
        """根据状态设置界面控件的可用性"""
        if state == 'initial':
            self.start_sniffing_btn.setEnabled(True)
            self.repeat_snatch_spinbox.setEnabled(True)
            self.browser_wait_spinbox.setEnabled(True)
            self.course_id_input.setEnabled(False)
            self.add_course_btn.setEnabled(False)
            self.remove_course_btn.setEnabled(False)
            self.start_snatching_btn.setEnabled(False)
            self.stop_snatching_btn.setEnabled(False)
        elif state == 'sniffing':
            self.start_sniffing_btn.setEnabled(False)
            self.browser_wait_spinbox.setEnabled(False)
        elif state == 'sniffed':
            self.start_sniffing_btn.setEnabled(False) # 登录一次即可
            self.browser_wait_spinbox.setEnabled(False)
            self.course_id_input.setEnabled(True)
            self.add_course_btn.setEnabled(True)
            self.remove_course_btn.setEnabled(True)
            self.start_snatching_btn.setEnabled(True)
            self.stop_snatching_btn.setEnabled(False)
        elif state == 'snatching':
            self.repeat_snatch_spinbox.setEnabled(False)
            self.course_id_input.setEnabled(False)
            self.add_course_btn.setEnabled(False)
            self.remove_course_btn.setEnabled(False)
            self.start_snatching_btn.setEnabled(False)
            self.stop_snatching_btn.setEnabled(True)

    @pyqtSlot(str)
    def update_log(self, text):
        self.log_browser.append(text.strip())
        self.log_browser.verticalScrollBar().setValue(self.log_browser.verticalScrollBar().maximum())

    @pyqtSlot(str)
    def show_error(self, text):
        self.update_log(f"错误: {text}")
        QMessageBox.warning(self, "发生错误", text)
        
    def start_sniffing(self):
        self.set_ui_state('sniffing')
        self.log_browser.clear()
        self.update_log("开始嗅探进程...")
        
        self.sniffer_thread = QThread()
        wait_time = self.browser_wait_spinbox.value()
        self.sniffer_worker = SnifferWorker(wait_time)
        self.sniffer_worker.moveToThread(self.sniffer_thread)

        self.sniffer_thread.started.connect(self.sniffer_worker.run)
        self.sniffer_worker.finished.connect(self.sniffer_thread.quit)
        self.sniffer_worker.finished.connect(self.sniffer_worker.deleteLater)
        self.sniffer_thread.finished.connect(self.sniffer_thread.deleteLater)
        
        self.sniffer_worker.log.connect(self.update_log)
        self.sniffer_worker.error.connect(self.show_error)
        self.sniffer_worker.data_captured.connect(self.on_data_captured)
        self.sniffer_thread.finished.connect(lambda: self.set_ui_state('sniffed' if self.headers else 'initial'))

        self.sniffer_thread.start()

    @pyqtSlot(dict)
    def on_data_captured(self, data):
        self.captured_data = data
        try:
            request_headers = self.captured_data.get('request_headers', {})
            cookie = get_header_case_insensitive(request_headers, 'cookie')
            token = get_header_case_insensitive(request_headers, 'token')
            missing_headers = [name for name, value in (('cookie', cookie), ('token', token)) if not value]
            if missing_headers:
                available_keys = ', '.join(request_headers.keys())
                raise KeyError(f"未找到请求头: {', '.join(missing_headers)}。实际可用请求头: {available_keys}")

            self.headers = {
                "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
                "cookie": cookie,
                "token": token
            }
            payload_params = parse_qs(self.captured_data.get('request_payload', ''))
            self.student_code = payload_params.get('xh', [None])[0]
            self.electiveBatchCode = payload_params.get('xklcdm', [None])[0]
            if not self.student_code or not self.electiveBatchCode:
                raise ValueError("无法从请求体解析到 xh 或 xklcdm，请确认触发了正确请求。")
            self.update_log(f"学号: {self.student_code}")
            self.update_log(f"选课批次代码: {self.electiveBatchCode}")
            self.update_log("凭据解析成功, 现在可以添加课程班号并开始抢课。")
            self.set_ui_state('sniffed')
        except Exception as e:
            self.show_error(f"解析捕获的数据时出错: {e}\n请确保已正确登录并触发了目标请求。")
            self.set_ui_state('initial')

    @pyqtSlot()
    def add_course(self):
        course_id = self.course_id_input.text().strip()
        if course_id:
            items = self.course_list_widget.findItems(course_id, Qt.MatchFlag.MatchExactly)
            if not items:
                self.course_list_widget.addItem(course_id)
                self.update_log(f"已添加班号: {course_id}")
            else:
                self.update_log(f"班号 {course_id} 已在列表中。")
            self.course_id_input.clear()
        else:
            self.show_error("请输入有效的课程班号。")

    @pyqtSlot()
    def remove_course(self):
        selected_items = self.course_list_widget.selectedItems()
        if not selected_items:
            self.show_error("请先在列表中选择要删除的班号。")
            return
        for item in selected_items:
            self.update_log(f"已移除班号: {item.text()}")
            self.course_list_widget.takeItem(self.course_list_widget.row(item))

    def start_snatching(self):
        if not self.headers:
            self.show_error("请先点击 '启动浏览器' 按钮完成登录，以获取抢课凭据。")
            return

        course_classid_list = [self.course_list_widget.item(i).text() for i in range(self.course_list_widget.count())]
        if not course_classid_list:
            self.show_error("请至少添加一个课程班号到待抢列表。")
            return
            
        self.set_ui_state('snatching')
        self.update_log("\n" + "="*40)
        self.update_log("即将开始抢课...")

        self.snatcher_thread = QThread()
        repeat_time = self.repeat_snatch_spinbox.value()
        self.snatcher_worker = SnatcherWorker(
            self.headers, self.student_code, self.electiveBatchCode,
            course_classid_list, repeat_time
        )
        self.snatcher_worker.moveToThread(self.snatcher_thread)

        self.snatcher_thread.started.connect(self.snatcher_worker.run)
        self.snatcher_worker.finished.connect(self.snatcher_thread.quit)
        self.snatcher_worker.finished.connect(self.snatcher_worker.deleteLater)
        self.snatcher_thread.finished.connect(lambda: self.set_ui_state('sniffed'))

        self.snatcher_worker.log.connect(self.update_log)
        self.snatcher_worker.error.connect(self.show_error)
        self.snatcher_thread.finished.connect(self.on_snatcher_finished)

        self.snatcher_thread.start()

    def stop_snatching(self):
        if self.snatcher_worker and self.snatcher_thread and self.snatcher_thread.isRunning():
            self.snatcher_worker.stop()
            # 工作线程会先完成当前步骤再停止，
            # 然后触发结束信号并执行清理流程。

    def on_snatcher_finished(self):
        """抢课任务完成后进行清理和UI更新。"""
        self.set_ui_state('sniffed')
        self.snatcher_thread = None
        self.snatcher_worker = None

    def closeEvent(self, event):
        """确保在关闭窗口时，后台线程也能正常退出"""
        if self.sniffer_thread and self.sniffer_thread.isRunning():
            self.sniffer_thread.quit()
            self.sniffer_thread.wait()
        if self.snatcher_thread and self.snatcher_thread.isRunning():
            self.snatcher_worker.stop()
            self.snatcher_thread.quit()
            self.snatcher_thread.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 
