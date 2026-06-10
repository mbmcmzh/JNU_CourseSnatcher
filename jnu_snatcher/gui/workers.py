"""GUI 后台工作线程。"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ..api import ApiError, CourseClient
from ..config import BASE_URL, REQUEST_INTERVAL, XKXF_URL
from ..credentials import CredentialError, Credentials
from ..sniffer import BrowserStartupError, RequestSniffer


class SnifferWorker(QObject):
    """启动浏览器嗅探并解析凭据。"""

    finished = pyqtSignal()
    log = pyqtSignal(str)
    credentials_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, browser_wait_time):
        super().__init__()
        self.browser_wait_time = browser_wait_time

    @pyqtSlot()
    def run(self):
        try:
            self.log.emit(f"请在 {self.browser_wait_time} 秒内完成登录操作...")
            sniffer = RequestSniffer(log=self.log.emit)
            captured = sniffer.sniff_requests(
                visit_url=BASE_URL,
                target_url=XKXF_URL,
                timeout=self.browser_wait_time,
            )
            if not captured:
                self.error.emit(f"在 {self.browser_wait_time} 秒内未捕获到登录凭据。")
                return

            credentials = Credentials.from_capture(captured)
            self.log.emit("凭据解析成功。")
            self.credentials_ready.emit(credentials)
        except BrowserStartupError as exc:
            self.error.emit(str(exc))
        except CredentialError as exc:
            self.error.emit(f"凭据解析失败: {exc}")
        except Exception as exc:  # 后台线程兜底，避免静默崩溃
            self.error.emit(f"嗅探过程中发生未知错误: {exc}")
        finally:
            self.finished.emit()


class SnatchWorker(QObject):
    """查询课程信息并循环执行抢课。"""

    finished = pyqtSignal()
    log = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, credentials, class_ids, rounds):
        super().__init__()
        self.credentials = credentials
        self.class_ids = class_ids
        self.rounds = rounds
        self._running = True

    @pyqtSlot()
    def stop(self):
        self._running = False
        self.log.emit("收到停止指令，正在结束当前步骤...")

    def _stopped(self):
        return not self._running

    @pyqtSlot()
    def run(self):
        try:
            client = CourseClient(self.credentials)

            self.log.emit("① 正在获取课程详细信息...")
            courses = []
            for class_id in self.class_ids:
                if self._stopped():
                    return
                try:
                    course = client.search_class(class_id)
                except ApiError as exc:
                    self.error.emit(str(exc))
                    continue
                courses.append(course)
                self.log.emit(f"   已确认 -> {course.summary}")

            if not courses:
                self.error.emit("未能获取任何有效的课程信息，抢课中止。")
                return

            self.log.emit(f"② 开始执行抢课，共 {self.rounds} 轮...")

            def on_result(course, result):
                if isinstance(result, Exception):
                    self.log.emit(f"   [{course.name}] 失败: {result}")
                else:
                    self.log.emit(f"   [{course.name}] {result}")

            import time

            for round_index in range(self.rounds):
                if self._stopped():
                    return
                self.log.emit(f"—— 第 {round_index + 1}/{self.rounds} 轮 ——")
                client.snatch_round(
                    courses,
                    on_result=on_result,
                    should_stop=self._stopped,
                )
                if self._stopped():
                    return
                if round_index < self.rounds - 1:
                    time.sleep(REQUEST_INTERVAL)

            self.log.emit("✓ 所有抢课轮次已完成。")
        except Exception as exc:  # 后台线程兜底，避免静默崩溃
            self.error.emit(f"抢课过程中发生未知错误: {exc}")
        finally:
            self.finished.emit()
