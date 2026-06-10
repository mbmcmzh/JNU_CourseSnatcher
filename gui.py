"""暨南大学抢课助手 —— 图形界面入口。"""

import sys

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
