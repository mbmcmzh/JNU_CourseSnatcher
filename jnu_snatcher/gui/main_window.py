"""主窗口。"""

from PyQt6.QtCore import QEvent, Qt, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizeGrip,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import DEFAULT_BROWSER_WAIT, DEFAULT_SNATCH_ROUNDS
from .workers import SnatchWorker, SnifferWorker

# 必须在 QApplication 创建前完成 QtWebEngine 的导入
try:
    from .embedded_browser import EmbeddedLoginDialog
except ImportError:
    EmbeddedLoginDialog = None

STATE_INITIAL = "initial"
STATE_SNIFFING = "sniffing"
STATE_READY = "ready"
STATE_SNATCHING = "snatching"

STATUS_TEXT = {
    STATE_INITIAL: ("未登录", "idle"),
    STATE_SNIFFING: ("等待登录…", "busy"),
    STATE_READY: ("凭据就绪", "ready"),
    STATE_SNATCHING: ("抢课中…", "busy"),
}


class TitleBar(QWidget):
    """无边框窗口的自定义标题栏：支持拖动与双击最大化。"""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        window = self.window()
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()
        super().mouseDoubleClickEvent(event)


def _card(title, hint=None):
    """构造一张带标题的圆角卡片，返回 (frame, body_layout)。"""
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)

    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    layout.addWidget(title_label)

    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("cardHint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

    return frame, layout


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("暨南大学抢课助手")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # 让窗口四角透明，根容器的圆角才能显示出来
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1000, 780)
        self.setMinimumSize(880, 700)

        self.credentials = None
        self.sniffer_thread = None
        self.sniffer_worker = None
        self.snatch_thread = None
        self.snatch_worker = None

        self._build_ui()
        self._set_state(STATE_INITIAL)
        self.append_log("界面初始化完成。")

    # ---------- 界面构建 ----------

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_title_bar())

        content = QVBoxLayout()
        content.setContentsMargins(28, 12, 28, 16)
        content.setSpacing(18)
        outer.addLayout(content, 1)

        content.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(18)
        content.addLayout(body, 1)

        body.addLayout(self._build_left_column(), 0)
        body.addWidget(self._build_log_card(), 1)

        # 无边框窗口右下角的缩放手柄
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 4, 4)
        grip_row.addStretch()
        grip_row.addWidget(QSizeGrip(root))
        outer.addLayout(grip_row)

    def _build_title_bar(self):
        bar = TitleBar()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(40)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(4)

        dot = QLabel()
        dot.setObjectName("titleDot")
        dot.setFixedSize(10, 10)
        layout.addWidget(dot)

        name = QLabel("暨南大学抢课助手")
        name.setObjectName("titleBarText")
        layout.addWidget(name)
        layout.addStretch()

        min_btn = QPushButton("—")
        min_btn.setObjectName("windowBtn")
        min_btn.clicked.connect(self.showMinimized)

        max_btn = QPushButton("□")
        max_btn.setObjectName("windowBtn")
        max_btn.clicked.connect(
            lambda: self.showNormal() if self.isMaximized() else self.showMaximized()
        )

        close_btn = QPushButton("✕")
        close_btn.setObjectName("windowCloseBtn")
        close_btn.clicked.connect(self.close)

        for btn in (min_btn, max_btn, close_btn):
            btn.setFixedSize(36, 28)
            layout.addWidget(btn)

        return bar

    def _build_header(self):
        header = QHBoxLayout()

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("暨南大学抢课助手")
        title.setObjectName("appTitle")
        subtitle = QLabel("登录获取凭据 → 添加教学班号 → 开始抢课")
        subtitle.setObjectName("appSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)

        header.addStretch()

        self.status_pill = QLabel()
        self.status_pill.setObjectName("statusPill")
        header.addWidget(self.status_pill, 0, Qt.AlignmentFlag.AlignTop)

        return header

    def _build_left_column(self):
        column = QVBoxLayout()
        column.setSpacing(14)

        # 第一步：登录
        login_card, login_layout = _card(
            "第一步 · 登录获取凭据",
            "在应用内登录选课系统，程序会自动捕获抢课所需凭据。",
        )
        self.embedded_btn = QPushButton("登录选课系统")
        self.embedded_btn.setObjectName("primary")
        self.embedded_btn.clicked.connect(self.start_embedded_login)
        if EmbeddedLoginDialog is None:
            self.embedded_btn.setToolTip("未安装 PyQt6-WebEngine，无法使用内嵌浏览器")
        login_layout.addWidget(self.embedded_btn)

        wait_row = QHBoxLayout()
        wait_label = QLabel("外置浏览器等待时间（秒）")
        wait_label.setObjectName("fieldLabel")
        self.wait_spin = QSpinBox()
        self.wait_spin.setRange(30, 600)
        self.wait_spin.setValue(DEFAULT_BROWSER_WAIT)
        wait_row.addWidget(wait_label)
        wait_row.addStretch()
        wait_row.addWidget(self.wait_spin)
        login_layout.addLayout(wait_row)

        self.sniff_btn = QPushButton("备用：外置 Chrome 登录")
        self.sniff_btn.clicked.connect(self.start_sniffing)
        login_layout.addWidget(self.sniff_btn)
        column.addWidget(login_card)

        # 第二步：班号
        course_card, course_layout = _card(
            "第二步 · 添加教学班号",
            "注意输入教学班号，而不是课程号。",
        )
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.class_input = QLineEdit()
        self.class_input.setPlaceholderText("输入教学班号，回车添加")
        self.class_input.returnPressed.connect(self.add_class_id)
        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self.add_class_id)
        input_row.addWidget(self.class_input, 1)
        input_row.addWidget(self.add_btn)
        course_layout.addLayout(input_row)

        self.class_list = QListWidget()
        self.class_list.setMinimumHeight(96)
        course_layout.addWidget(self.class_list, 1)

        self.remove_btn = QPushButton("删除选中项")
        self.remove_btn.setObjectName("ghost")
        self.remove_btn.clicked.connect(self.remove_class_id)
        course_layout.addWidget(self.remove_btn, 0, Qt.AlignmentFlag.AlignRight)
        column.addWidget(course_card, 1)

        # 第三步：执行
        run_card, run_layout = _card("第三步 · 开始抢课")
        rounds_row = QHBoxLayout()
        rounds_label = QLabel("抢课轮数")
        rounds_label.setObjectName("fieldLabel")
        self.rounds_spin = QSpinBox()
        self.rounds_spin.setRange(1, 100)
        self.rounds_spin.setValue(DEFAULT_SNATCH_ROUNDS)
        rounds_row.addWidget(rounds_label)
        rounds_row.addStretch()
        rounds_row.addWidget(self.rounds_spin)
        run_layout.addLayout(rounds_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.start_btn = QPushButton("开始抢课")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self.start_snatching)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self.stop_snatching)
        action_row.addWidget(self.start_btn, 1)
        action_row.addWidget(self.stop_btn)
        run_layout.addLayout(action_row)
        column.addWidget(run_card)

        return column

    def _build_log_card(self):
        log_card, log_layout = _card("运行日志")

        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(lambda: self.log_view.clear())
        # 把清空按钮放到卡片标题同一行
        title_row = log_layout.itemAt(0).widget()
        header_row = QHBoxLayout()
        log_layout.removeWidget(title_row)
        header_row.addWidget(title_row)
        header_row.addStretch()
        header_row.addWidget(clear_btn)
        log_layout.insertLayout(0, header_row)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view, 1)

        return log_card

    def changeEvent(self, event):
        # 最大化铺满屏幕时去掉圆角，恢复时再加回来。
        # 注意不能叫 "maximized"：那是 QWidget 内置只读属性，写不进去。
        if event.type() == QEvent.Type.WindowStateChange:
            root = self.centralWidget()
            root.setProperty("winMaximized", self.isMaximized())
            root.style().unpolish(root)
            root.style().polish(root)
        super().changeEvent(event)

    # ---------- 状态管理 ----------

    def _set_state(self, state):
        self.state = state
        text, kind = STATUS_TEXT[state]
        self.status_pill.setText(text)
        self.status_pill.setProperty("state", kind)
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)

        is_initial = state == STATE_INITIAL
        is_ready = state == STATE_READY
        is_snatching = state == STATE_SNATCHING

        self.embedded_btn.setEnabled(is_initial and EmbeddedLoginDialog is not None)
        self.sniff_btn.setEnabled(is_initial)
        self.wait_spin.setEnabled(is_initial)
        self.class_input.setEnabled(is_ready)
        self.add_btn.setEnabled(is_ready)
        self.remove_btn.setEnabled(is_ready)
        self.rounds_spin.setEnabled(is_ready)
        self.start_btn.setEnabled(is_ready)
        self.stop_btn.setEnabled(is_snatching)

    # ---------- 日志 ----------

    @pyqtSlot(str)
    def append_log(self, text):
        text = text.strip()
        if not text:
            return
        self.log_view.append(text)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot(str)
    def show_error(self, text):
        self.append_log(f"⚠ {text}")

    def _show_error_dialog(self, text):
        self.show_error(text)
        QMessageBox.warning(self, "发生错误", text)

    # ---------- 第一步：内嵌浏览器登录 ----------

    def start_embedded_login(self):
        if EmbeddedLoginDialog is None:
            self._show_error_dialog("未安装 PyQt6-WebEngine，请使用外置 Chrome 登录。")
            return

        self._set_state(STATE_SNIFFING)
        self.append_log("已打开内嵌浏览器，请完成登录...")

        try:
            dialog = EmbeddedLoginDialog(self)
        except Exception as exc:  # WebEngine 运行时初始化失败兜底，避免界面卡死
            self.show_error(f"内嵌浏览器启动失败：{exc}")
            self._set_state(STATE_INITIAL)
            return

        dialog.log.connect(self.append_log)
        dialog.credentials_captured.connect(self.on_credentials_ready)
        dialog.exec()
        # 对话框是主窗口的子对象，不主动释放会带着 WebEngine 资源活到退出
        dialog.deleteLater()

        if not self.credentials:
            self.append_log("登录窗口已关闭，未捕获到凭据。")
        self._set_state(STATE_READY if self.credentials else STATE_INITIAL)

    # ---------- 第一步（备用）：外置浏览器嗅探 ----------

    def start_sniffing(self):
        self._set_state(STATE_SNIFFING)
        self.append_log("开始启动浏览器嗅探器...")

        self.sniffer_thread = QThread()
        self.sniffer_worker = SnifferWorker(self.wait_spin.value())
        self.sniffer_worker.moveToThread(self.sniffer_thread)

        self.sniffer_thread.started.connect(self.sniffer_worker.run)
        self.sniffer_worker.finished.connect(self.sniffer_thread.quit)
        self.sniffer_worker.finished.connect(self.sniffer_worker.deleteLater)
        self.sniffer_thread.finished.connect(self.sniffer_thread.deleteLater)
        self.sniffer_thread.finished.connect(self.on_sniffer_finished)

        self.sniffer_worker.log.connect(self.append_log)
        self.sniffer_worker.error.connect(self.show_error)
        self.sniffer_worker.credentials_ready.connect(self.on_credentials_ready)

        self.sniffer_thread.start()

    @pyqtSlot(object)
    def on_credentials_ready(self, credentials):
        self.credentials = credentials
        self.append_log(f"学号: {credentials.student_code}")
        self.append_log(f"选课批次代码: {credentials.elective_batch_code}")
        self.append_log("现在可以添加课程班号并开始抢课。")

    def on_sniffer_finished(self):
        self.sniffer_thread = None
        self.sniffer_worker = None
        self._set_state(STATE_READY if self.credentials else STATE_INITIAL)

    # ---------- 第二步：班号 ----------

    def add_class_id(self):
        class_id = self.class_input.text().strip()
        if not class_id:
            self._show_error_dialog("请输入有效的教学班号。")
            return
        if self.class_list.findItems(class_id, Qt.MatchFlag.MatchExactly):
            self.append_log(f"班号 {class_id} 已在列表中。")
        else:
            self.class_list.addItem(class_id)
            self.append_log(f"已添加班号: {class_id}")
        self.class_input.clear()

    def remove_class_id(self):
        selected = self.class_list.selectedItems()
        if not selected:
            self._show_error_dialog("请先在列表中选择要删除的班号。")
            return
        for item in selected:
            self.append_log(f"已移除班号: {item.text()}")
            self.class_list.takeItem(self.class_list.row(item))

    # ---------- 第三步：抢课 ----------

    def start_snatching(self):
        if not self.credentials:
            self._show_error_dialog("请先完成登录以获取抢课凭据。")
            return

        class_ids = [self.class_list.item(i).text() for i in range(self.class_list.count())]
        if not class_ids:
            self._show_error_dialog("请至少添加一个课程班号。")
            return

        self._set_state(STATE_SNATCHING)
        self.append_log("=" * 36)
        self.append_log("即将开始抢课...")

        self.snatch_thread = QThread()
        self.snatch_worker = SnatchWorker(self.credentials, class_ids, self.rounds_spin.value())
        self.snatch_worker.moveToThread(self.snatch_thread)

        self.snatch_thread.started.connect(self.snatch_worker.run)
        self.snatch_worker.finished.connect(self.snatch_thread.quit)
        self.snatch_worker.finished.connect(self.snatch_worker.deleteLater)
        self.snatch_thread.finished.connect(self.snatch_thread.deleteLater)
        self.snatch_thread.finished.connect(self.on_snatch_finished)

        self.snatch_worker.log.connect(self.append_log)
        self.snatch_worker.error.connect(self.show_error)

        self.snatch_thread.start()

    def stop_snatching(self):
        if self.snatch_worker and self.snatch_thread and self.snatch_thread.isRunning():
            self.snatch_worker.stop()

    def on_snatch_finished(self):
        self.snatch_thread = None
        self.snatch_worker = None
        self._set_state(STATE_READY)

    # ---------- 关闭 ----------

    def closeEvent(self, event):
        if self.snatch_thread and self.snatch_thread.isRunning():
            self.snatch_worker.stop()
            self.snatch_thread.quit()
            self.snatch_thread.wait(3000)
        if self.sniffer_thread and self.sniffer_thread.isRunning():
            self.sniffer_thread.quit()
            self.sniffer_thread.wait(3000)
        event.accept()
