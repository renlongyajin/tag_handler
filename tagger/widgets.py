from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, QSize, QRectF, pyqtSignal, QSignalBlocker
from PyQt5.QtGui import QColor, QPainter, QPixmap, QTransform
from PyQt5.QtWidgets import QFrame, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QToolButton, QWidget


class TagRowWidget(QFrame):
    editCommitted = pyqtSignal(int, str, str, str)
    deleteRequested = pyqtSignal(int)
    ROW_HEIGHT = 48

    def __init__(
        self, entry_id: int, english: str, chinese: str, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.entry_id = entry_id
        self.setObjectName("TagRow")
        self.setStyleSheet(
            """
QFrame#TagRow {
    border: 1px solid #c2b38f;
    border-radius: 8px;
    background-color: #f4f1e1;
}
QFrame#TagRow[focused="true"] {
    border: 2px solid #7fb069;
}
QLineEdit {
    border: none;
    color: #2f5130;
    background: transparent;
    font-size: 18px;
    font-weight: 600;
}
QToolButton {
    border: none;
    color: #8a5f3d;
    padding: 0 6px;
    font-size: 18px;
    font-weight: 600;
}
QToolButton:hover {
    color: #5a3b22;
}
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self.ROW_HEIGHT)

        self._cache = {"english": english, "chinese": chinese}

        self.label_en = QLabel("", self)
        self.label_en.setStyleSheet("color:#795548;font-weight:700;font-size:16px;")
        layout.addWidget(self.label_en)

        self.edit_en = QLineEdit(english, self)
        self.edit_en.setPlaceholderText("英文标签")
        self.edit_en.editingFinished.connect(lambda: self._commit("english"))
        layout.addWidget(self.edit_en, 1)

        self.label_zh = QLabel("", self)
        self.label_zh.setStyleSheet("color:#33691e;font-weight:700;font-size:16px;")
        layout.addWidget(self.label_zh)

        self.edit_zh = QLineEdit(chinese, self)
        self.edit_zh.setPlaceholderText("中文翻译")
        self.edit_zh.editingFinished.connect(lambda: self._commit("chinese"))
        layout.addWidget(self.edit_zh, 1)

        self.remove_button = QToolButton(self)
        self.remove_button.setText("×")
        self.remove_button.clicked.connect(self._emit_delete)
        layout.addWidget(self.remove_button)

    def set_entry(self, entry_id: int, english: str, chinese: str) -> None:
        self.entry_id = entry_id
        self.set_texts(english, chinese)

    def set_texts(self, english: str, chinese: str) -> None:
        if self.edit_en.text() != english:
            blocker_en = QSignalBlocker(self.edit_en)
            self.edit_en.setText(english)
            del blocker_en
        if self.edit_zh.text() != chinese:
            blocker_zh = QSignalBlocker(self.edit_zh)
            self.edit_zh.setText(chinese)
            del blocker_zh
        self._cache["english"] = english
        self._cache["chinese"] = chinese

    def focusInEvent(self, event) -> None:
        self.setProperty("focused", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self.setProperty("focused", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusOutEvent(event)

    def _commit(self, field: str) -> None:
        editor = self.edit_en if field == "english" else self.edit_zh
        new_text = editor.text()
        old_text = self._cache[field]
        if new_text != old_text:
            self._cache[field] = new_text
            self.editCommitted.emit(self.entry_id, field, old_text, new_text)

    def _emit_delete(self) -> None:
        self.deleteRequested.emit(self.entry_id)

    def set_locked(self, locked: bool) -> None:
        self.edit_en.setReadOnly(locked)
        self.edit_zh.setReadOnly(locked)
        self.remove_button.setEnabled(not locked)


class ImageViewer(QGraphicsView):
    zoomChanged = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pix_item: Optional[QGraphicsPixmapItem] = None
        self.zoom = 1.0
        self.min_zoom = 0.3
        self.max_zoom = 3.0
        self.base_transform = QTransform()

        self.setBackgroundBrush(QColor("#161616"))
        self.setRenderHint(QPainter.Antialiasing, False)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def load_image(self, path: Optional[str]) -> None:
        self.scene.clear()
        self.pix_item = None
        if not path:
            self._reset_zoom()
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._reset_zoom()
            return
        self.pix_item = self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self._fit_to_view()

    def wheelEvent(self, event) -> None:
        if not self.pix_item:
            return
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 1 / 1.1
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        if new_zoom == self.zoom:
            return
        self.zoom = new_zoom
        self._apply_zoom()

    def mouseDoubleClickEvent(self, event) -> None:
        self._fit_to_view()
        super().mouseDoubleClickEvent(event)

    def _apply_zoom(self) -> None:
        if not self.pix_item:
            return
        transform = QTransform(self.base_transform)
        transform.scale(self.zoom, self.zoom)
        self.setTransform(transform)
        self.zoomChanged.emit(self.zoom)

    def _reset_zoom(self) -> None:
        self.zoom = 1.0
        self._apply_zoom()

    def zoom_percent(self) -> int:
        return int(self.zoom * 100)

    def _fit_to_view(self) -> None:
        if not self.pix_item:
            self.resetTransform()
            self.base_transform = QTransform()
            self.zoom = 1.0
            self.zoomChanged.emit(self.zoom)
            return
        self.resetTransform()
        self.fitInView(self.pix_item, Qt.KeepAspectRatio)
        self.base_transform = self.transform()
        self.zoom = 1.0
        self.zoomChanged.emit(self.zoom)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.pix_item and self.zoom == 1.0:
            self._fit_to_view()
