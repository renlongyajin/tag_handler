from __future__ import annotations

from PyQt5.QtWidgets import QApplication

from .main_window import TagEditorMainWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = TagEditorMainWindow()
    window.showMaximized()
    app.exec_()
