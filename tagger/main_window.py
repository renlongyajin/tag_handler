from __future__ import annotations

import itertools
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

import json
import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSplitter,
    QStatusBar,
    QToolBar,
    QToolButton,
    QUndoStack,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .commands import (
    AddTagCommand,
    ModifyTagCommand,
    RemoveTagCommand,
    ReplaceAllTagsCommand,
)
from .config import DEFAULT_DIRECTORY, DEFAULT_TAG_SUFFIX
from .dto import FileRecord, TagEntry
from .fileops import discover_records, read_tags, write_tags, set_locked, is_locked
from .translation import TranslationManager
from .utils import normalize
from .widgets import ImageViewer, TagRowWidget


class TagEditorMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("标签校准工具")
        self.resize(1400, 900)
        self.translator = TranslationManager()
        self.undo_stack = QUndoStack(self)
        self.tag_suffix = DEFAULT_TAG_SUFFIX
        self.root_dir: Optional[Path] = None
        self.records: List[FileRecord] = []
        self.current_index: Optional[int] = None
        self.current_record: Optional[FileRecord] = None
        self.current_tags: List[TagEntry] = []
        self.initial_tags: List[str] = []
        self._id_counter = itertools.count(1)
        self.current_locked: bool = False
        self.copied_pairs: List[Tuple[str, str]] = []
        self._build_layout()
        self._build_toolbar()
        self._bind_signals()
        self._bind_shortcuts()
        self.undo_stack.cleanChanged.connect(self._on_clean_changed)
        self.statusBar().showMessage("请选择目录以开始")
        self.choose_directory(initial=True)

    def _build_layout(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        wrapper = QHBoxLayout(central)
        wrapper.setContentsMargins(6, 6, 6, 6)
        wrapper.setSpacing(6)
        splitter = QSplitter(Qt.Horizontal, self)
        wrapper.addWidget(splitter)

        tag_panel = QWidget(splitter)
        tag_layout = QVBoxLayout(tag_panel)
        tag_layout.setContentsMargins(8, 8, 8, 8)
        tag_layout.setSpacing(6)

        self.file_label = QLabel("当前文件：无", tag_panel)
        tag_layout.addWidget(self.file_label)

        self.tag_scroll = QScrollArea(tag_panel)
        self.tag_scroll.setWidgetResizable(True)
        self.tag_container = QWidget()
        self.tag_layout = QGridLayout(self.tag_container)
        self.tag_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_layout.setHorizontalSpacing(12)
        self.tag_layout.setVerticalSpacing(8)
        self.tag_scroll.setWidget(self.tag_container)
        tag_layout.addWidget(self.tag_scroll, 1)

        buttons = QWidget(tag_panel)
        btn_layout = QHBoxLayout(buttons)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)
        self.btn_add = QPushButton("添加标签", buttons)
        self.btn_retranslate = QPushButton("重新翻译", buttons)
        self.btn_restore = QPushButton("恢复初始", buttons)
        self.btn_copy = QPushButton("复制当前标签", buttons)
        self.btn_paste = QPushButton("粘贴标签到当前", buttons)
        self.btn_compact = QPushButton("精简标签", buttons)
        self.btn_toggle_lock = QPushButton("锁定标签", buttons)
        self.btn_next_unlocked = QPushButton("下一个未锁定", buttons)
        for btn in (
            self.btn_add,
            self.btn_retranslate,
            self.btn_restore,
            self.btn_copy,
            self.btn_paste,
            self.btn_compact,
            self.btn_toggle_lock,
            self.btn_next_unlocked,
        ):
            btn_layout.addWidget(btn)
        tag_layout.addWidget(buttons)

        splitter.addWidget(tag_panel)

        viewer_panel = QWidget(splitter)
        viewer_layout = QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(8, 8, 8, 8)
        viewer_layout.setSpacing(6)
        self.viewer = ImageViewer(viewer_panel)
        viewer_layout.addWidget(self.viewer)
        splitter.addWidget(viewer_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 600])

        self.tag_widgets: List[TagRowWidget] = []

    def _build_toolbar(self) -> None:
        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, slot in (
            ("选目录", self.choose_directory),
            ("打开标签文件", self.open_tag_file),
            ("保存", self.save_current_file),
        ):
            action = QAction(text, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)

        add_action = QAction("批量添加标签", self)
        add_action.triggered.connect(self.bulk_add_tags)
        toolbar.addAction(add_action)

        replace_action = QAction("批量替换标签", self)
        replace_action.triggered.connect(self.bulk_replace_tag)
        toolbar.addAction(replace_action)

        delete_action = QAction("批量删除标签", self)
        delete_action.triggered.connect(self.bulk_delete_tag)
        toolbar.addAction(delete_action)

        lock_all_action = QAction("锁定全部", self)
        lock_all_action.triggered.connect(lambda: self._lock_or_unlock_all(True))
        toolbar.addAction(lock_all_action)

        range_lock_action = QAction("范围锁定", self)
        range_lock_action.triggered.connect(self._lock_range_dialog)
        toolbar.addAction(range_lock_action)

        delete_reindex_action = QAction("删除并重排", self)
        delete_reindex_action.triggered.connect(self._delete_and_reindex)
        toolbar.addAction(delete_reindex_action)

        unlock_all_action = QAction("解锁全部", self)
        unlock_all_action.triggered.connect(lambda: self._lock_or_unlock_all(False))
        toolbar.addAction(unlock_all_action)

        stats_action = QAction("锁定统计", self)
        stats_action.triggered.connect(self._show_lock_stats)
        toolbar.addAction(stats_action)

        export_menu = QMenu("导出", self)
        export_all_json_action = export_menu.addAction("导出全部标签（JSON）")
        export_all_json_action.triggered.connect(self._export_all_tags)
        export_locked_json_action = export_menu.addAction("导出已锁定标签（JSON）")
        export_locked_json_action.triggered.connect(self._export_locked_tags)
        export_all_txt_action = export_menu.addAction("导出全部标签（TXT）")
        export_all_txt_action.triggered.connect(self._export_all_tags_txt)
        export_images_action = export_menu.addAction("导出全部图片")
        export_images_action.triggered.connect(self._export_all_images)

        export_button = QToolButton(self)
        export_button.setText("导出")
        export_button.setPopupMode(QToolButton.InstantPopup)
        export_button.setMenu(export_menu)
        toolbar.addWidget(export_button)

        self.action_undo = self.undo_stack.createUndoAction(self, "撤销")
        self.action_undo = self.undo_stack.createUndoAction(self, "撤销")
        self.action_undo.setShortcut(QKeySequence("Ctrl+Z"))
        toolbar.addAction(self.action_undo)

        self.action_redo = self.undo_stack.createRedoAction(self, "重做")
        self.action_redo.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        toolbar.addAction(self.action_redo)


        suffix_action = QAction("设置后缀", self)
        suffix_action.triggered.connect(self.set_tag_suffix)
        toolbar.addAction(suffix_action)

        self.setStatusBar(QStatusBar(self))
    def _bind_signals(self) -> None:
        self.btn_add.clicked.connect(self._handle_add)
        self.btn_retranslate.clicked.connect(self._handle_retranslate)
        self.btn_restore.clicked.connect(self.restore_initial)
        self.btn_copy.clicked.connect(self.copy_current_tags)
        self.btn_paste.clicked.connect(self.paste_tags_into_current)
        self.btn_compact.clicked.connect(self._compact_current_tags)
        self.btn_toggle_lock.clicked.connect(self.toggle_lock_current)
        self.btn_next_unlocked.clicked.connect(self.open_next_unlocked)
        self.viewer.zoomChanged.connect(lambda _: self._update_status())

    def _bind_shortcuts(self) -> None:
        QShortcut(Qt.Key_Right, self, activated=self.open_next)
        QShortcut(Qt.Key_Left, self, activated=self.open_previous)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_current_file)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.choose_directory)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, activated=self.open_tag_file)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.toggle_lock_current)

    def choose_directory(self, initial: bool = False) -> None:
        start = str(self.root_dir or DEFAULT_DIRECTORY)
        path = QFileDialog.getExistingDirectory(self, "选择目录", start)
        if not path:
            if initial and not self.records:
                self.close()
            return
        self.load_directory(Path(path))

    def load_directory(self, folder: Path, select_tag: Optional[Path] = None) -> None:
        if not folder.is_dir():
            QMessageBox.warning(self, "目录无效", "所选路径不是目录。"); return
        if not self.ensure_saved():
            return
        self.root_dir = folder
        self.records = discover_records(folder, self.tag_suffix)
        if not self.records:
            self.current_index = None
            self.current_record = None
            self.current_tags.clear()
            self.initial_tags.clear()
            self._clear_tag_widgets()
            self.viewer.load_image(None)
            self.current_locked = False
            self._apply_lock_state()
            self.statusBar().showMessage("未找到可用文件。"); return
        target = 0
        if select_tag:
            target_path = select_tag.resolve()
            for idx, record in enumerate(self.records):
                if record.tag_path.resolve() == target_path:
                    target = idx; break
        self.open_index(target)

    def _clear_tag_widgets(self) -> None:
        while self.tag_layout.count():
            item = self.tag_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.tag_widgets.clear()

    def _populate_tag_widgets(self) -> None:
        self._clear_tag_widgets()
        for idx, entry in enumerate(self.current_tags):
            widget = TagRowWidget(entry.entry_id, entry.english, entry.chinese)
            widget.editCommitted.connect(self._handle_edit)
            widget.deleteRequested.connect(self._handle_delete)
            row, col = divmod(idx, 2)
            self.tag_layout.addWidget(widget, row, col)
            self.tag_widgets.append(widget)
        self.tag_layout.setColumnStretch(0, 1)
        self.tag_layout.setColumnStretch(1, 1)
        total_rows = (len(self.current_tags) + 1) // 2
        for row in range(total_rows):
            self.tag_layout.setRowMinimumHeight(row, TagRowWidget.ROW_HEIGHT)
            self.tag_layout.setRowStretch(row, 0)
        self.tag_layout.setRowStretch(total_rows, 1)

    def _apply_entry_pairs(self, pairs: List[Tuple[str, str]]) -> None:
        self.current_tags = [
            TagEntry(idx + 1, english, chinese) for idx, (english, chinese) in enumerate(pairs)
        ]
        self._id_counter = itertools.count(len(self.current_tags) + 1)
        self.refresh_lists()

    def _reload_current_tags(self, english_tags: List[str]) -> None:
        self.initial_tags = english_tags[:]
        translations = self.translator.translate_many(english_tags, "en", "zh")
        self.current_tags = [
            TagEntry(idx + 1, en, zh)
            for idx, (en, zh) in enumerate(zip(english_tags, translations))
        ]
        self._id_counter = itertools.count(len(self.current_tags) + 1)
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self.refresh_lists()

    def _prompt_bulk_add(self) -> Optional[Tuple[List[str], bool]]:
        dialog = QDialog(self)
        dialog.setWindowTitle("批量添加标签")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        input_edit = QLineEdit(dialog)
        form.addRow("待添加标签：", input_edit)
        layout.addLayout(form)
        hint = QLabel("多个标签可用逗号、空格或换行分隔。", dialog)
        layout.addWidget(hint)
        include_locked_box = QCheckBox("涉及已锁定的文件", dialog)
        layout.addWidget(include_locked_box)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() != QDialog.Accepted:
            return None
        raw = input_edit.text()
        parts = [normalize(piece) for piece in re.split(r"[,\s]+", raw) if piece.strip()]
        tags: List[str] = []
        for item in parts:
            if item and item not in tags:
                tags.append(item)
        if not tags:
            QMessageBox.information(self, "批量添加标签", "未提供有效的标签。")
            return None
        return tags, include_locked_box.isChecked()

    def _prompt_bulk_replace(self) -> Optional[Tuple[str, str, bool]]:
        dialog = QDialog(self)
        dialog.setWindowTitle("批量替换标签")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        source_edit = QLineEdit(dialog)
        target_edit = QLineEdit(dialog)
        form.addRow("待替换标签：", source_edit)
        form.addRow("目标标签：", target_edit)
        layout.addLayout(form)
        include_locked_box = QCheckBox("涉及已锁定的文件", dialog)
        layout.addWidget(include_locked_box)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() != QDialog.Accepted:
            return None
        source_tag = normalize(source_edit.text())
        target_tag = normalize(target_edit.text())
        if not source_tag or not target_tag:
            QMessageBox.information(self, "批量替换标签", "请同时提供有效的原标签和目标标签。")
            return None
        if source_tag == target_tag:
            QMessageBox.information(self, "批量替换标签", "原标签与目标标签相同，无需替换。")
            return None
        return source_tag, target_tag, include_locked_box.isChecked()

    def _prompt_bulk_delete(self) -> Optional[Tuple[str, bool]]:
        dialog = QDialog(self)
        dialog.setWindowTitle("批量删除标签")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        tag_edit = QLineEdit(dialog)
        form.addRow("待删除标签：", tag_edit)
        layout.addLayout(form)
        include_locked_box = QCheckBox("涉及已锁定的文件", dialog)
        layout.addWidget(include_locked_box)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() != QDialog.Accepted:
            return None
        tag = normalize(tag_edit.text())
        if not tag:
            QMessageBox.information(self, "批量删除标签", "未提供有效的标签。")
            return None
        return tag, include_locked_box.isChecked()

    def _parse_tag_text(self, text: str) -> List[str]:
        parts = text.replace("\n", ",").split(",")
        return [normalize(part) for part in parts if normalize(part)]


    @staticmethod
    def _normalize_tag_key(tag: str) -> str:
        value = tag.strip().lower()
        if len(value) > 3 and value.endswith('ies'):
            return value[:-3] + 'y'
        if len(value) > 3 and value.endswith(('ses', 'xes', 'zes', 'ches', 'shes')):
            return value[:-2]
        if len(value) > 3 and value.endswith('s') and not value.endswith('ss'):
            return value[:-1]
        return value

    @staticmethod
    def _is_plural_tag(tag: str) -> bool:
        value = tag.strip().lower()
        if len(value) > 3 and value.endswith('ies'):
            return True
        if len(value) > 3 and value.endswith(('ses', 'xes', 'zes', 'ches', 'shes')):
            return True
        if len(value) > 3 and value.endswith('s') and not value.endswith('ss'):
            return True
        return False

    def _tags_equivalent(self, first: str, second: str) -> bool:
        return self._normalize_tag_key(first) == self._normalize_tag_key(second)

    def _can_accept_new_tag(self, english: str, exclude_entry_id: Optional[int] = None) -> bool:
        key = self._normalize_tag_key(english)
        for entry in self.current_tags:
            if exclude_entry_id and entry.entry_id == exclude_entry_id:
                continue
            if self._normalize_tag_key(entry.english) == key:
                return False
        return True

    def _deduplicate_tag_pairs(
        self, pairs: List[Tuple[str, str]]
    ) -> Tuple[List[Tuple[str, str]], bool]:
        result: List[Tuple[str, str]] = []
        seen: dict[str, int] = {}
        changed = False
        for english, chinese in pairs:
            clean_en = english.strip()
            clean_zh = chinese.strip()
            if not clean_en:
                changed = True
                continue
            key = self._normalize_tag_key(clean_en)
            index = seen.get(key)
            if index is None:
                result.append((clean_en, clean_zh))
                seen[key] = len(result) - 1
                continue
            existing_en, existing_zh = result[index]
            if not self._is_plural_tag(existing_en) and self._is_plural_tag(clean_en):
                result[index] = (clean_en, clean_zh)
            changed = True
        return result, changed

    def _compact_current_tags(self) -> None:
        if self.current_locked:
            self._editing_locked_warning()
            return
        if not self.current_tags:
            QMessageBox.information(self, "精简标签", "当前没有可精简的标签。")
            return
        pairs = [(entry.english, entry.chinese) for entry in self.current_tags]
        deduped, changed = self._deduplicate_tag_pairs(pairs)
        if not changed:
            self.statusBar().showMessage("标签已处于精简状态。", 3000)
            return
        self.undo_stack.push(ReplaceAllTagsCommand(self, deduped))
        self.statusBar().showMessage("已精简标签列表。", 3000)

    def _apply_lock_state(self) -> None:
        locked = self.current_locked
        for widget in self.tag_widgets:
            widget.set_locked(locked)
        self.btn_add.setEnabled(not locked)
        self.btn_retranslate.setEnabled(not locked)
        self.btn_restore.setEnabled(not locked)
        self.btn_paste.setEnabled(not locked)
        self.btn_next_unlocked.setEnabled(bool(self.records))
        lock_text = "🔒 取消锁定" if locked else "🔓 锁定标签"
        self.btn_toggle_lock.setText(lock_text)
        self.btn_toggle_lock.setEnabled(self.current_record is not None)
        if hasattr(self, "action_undo"):
            self.action_undo.setEnabled(not locked)
        if hasattr(self, "action_redo"):
            self.action_redo.setEnabled(not locked)
        # 只读状态下仍允许复制标签
        self.btn_copy.setEnabled(True)

    def _editing_locked_warning(self) -> None:
        self.statusBar().showMessage("🔒 当前文件已锁定，如需继续编辑请先取消标记。", 3000)

    def copy_current_tags(self) -> None:
        if not self.current_tags:
            QMessageBox.information(self, "复制标签", "当前没有可复制的标签。")
            return
        self.copied_pairs = [
            (entry.english, entry.chinese) for entry in self.current_tags if entry.english.strip()
        ]
        QApplication.clipboard().setText(", ".join(en for en, _ in self.copied_pairs))
        self.statusBar().showMessage("已复制当前标签（英文）到剪贴板。", 3000)

    def paste_tags_into_current(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "粘贴标签", "请先打开一个标签文件。")
            return
        if self.current_locked:
            self._editing_locked_warning()
            return
        pairs = list(self.copied_pairs)
        if not pairs:
            clipboard_text = QApplication.clipboard().text()
            english_tags = self._parse_tag_text(clipboard_text)
            if english_tags:
                translations = self.translator.translate_many(english_tags, "en", "zh")
                pairs = list(zip(english_tags, translations))
        if not pairs:
            QMessageBox.information(self, "粘贴标签", "剪贴板中没有可用的标签。")
            return
        self.undo_stack.push(ReplaceAllTagsCommand(self, pairs))

    def toggle_lock_current(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "标记标签", "请先打开一个标签文件。")
            return
        new_state = not self.current_locked
        if new_state and not self.undo_stack.isClean():
            if not self.save_current_file():
                return
        try:
            set_locked(self.current_record.tag_path, new_state)
        except OSError as exc:
            QMessageBox.warning(self, "标记标签", f"操作失败：{exc}")
            return
        self.current_locked = new_state
        self.records[self.current_index].locked = new_state
        if new_state:
            self.undo_stack.clear()
            self.undo_stack.setClean()
        icon_msg = "🔒 已锁定当前文件" if new_state else "🔓 已解除锁定，可继续编辑"
        self._apply_lock_state()
        self._update_status()
        self.statusBar().showMessage(icon_msg, 3000)

    def _lock_range_dialog(self) -> None:
        if not self.records:
            QMessageBox.information(self, "范围锁定", "当前没有可处理的文件。")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("范围锁定")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        start_spin = QSpinBox(dialog)
        start_spin.setRange(1, len(self.records))
        default_start = (self.current_index + 1) if self.current_index is not None else 1
        start_spin.setValue(default_start)
        end_spin = QSpinBox(dialog)
        end_spin.setRange(1, len(self.records))
        end_spin.setValue(len(self.records))
        form.addRow("起始序号：", start_spin)
        form.addRow("结束序号：", end_spin)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return

        start = start_spin.value()
        end = end_spin.value()
        if start > end:
            start, end = end, start

        if (
            self.current_record
            and start <= self.current_index + 1 <= end
            and not self.save_current_file(auto=True)
        ):
            return

        success = 0
        failures: List[str] = []
        for idx in range(start - 1, end):
            record = self.records[idx]
            try:
                set_locked(record.tag_path, True)
                record.locked = True
                success += 1
            except OSError as exc:
                failures.append(f"{record.base_name}: {exc}")

        if self.current_record and start - 1 <= self.current_index <= end - 1:
            self.current_locked = True
            self.records[self.current_index].locked = True
        elif self.current_record:
            self.current_locked = is_locked(self.current_record.tag_path)
            self.records[self.current_index].locked = self.current_locked

        self._apply_lock_state()
        self._update_status()

        total = end - start + 1
        message = f"范围锁定完成：{success}/{total} 个文件已锁定。"
        if failures:
            failure_list = "\n".join(failures[:10])
            message += f"\n\n失败文件（最多显示 10 条）：\n{failure_list}"
        QMessageBox.information(self, "范围锁定", message)

    def _delete_and_reindex(self) -> None:
        if not self.records:
            QMessageBox.information(self, "删除并重排", "当前没有可处理的文件。")
            return
        if not self.ensure_saved():
            return
        default_base = self.current_record.base_name if self.current_record else self.records[0].base_name
        text, ok = QInputDialog.getText(
            self,
            "删除并重排",
            "请输入要删除的序号（例如 051）：",
            text=default_base,
        )
        if not ok:
            return
        base = text.strip()
        if not base:
            QMessageBox.information(self, "删除并重排", "未提供有效的序号。")
            return
        try:
            target_idx = next(i for i, record in enumerate(self.records) if record.base_name == base)
        except StopIteration:
            QMessageBox.warning(self, "删除并重排", f"未找到名为 {base} 的文件。")
            return
        confirm = QMessageBox.question(
            self,
            "删除并重排",
            f"确定要删除 {base} 及其所有同名文件并重排后续序号吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        folder = self.root_dir
        if folder is None:
            QMessageBox.warning(self, "删除并重排", "当前目录无效。")
            return
        deletion_errors: List[str] = []
        for path in folder.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if name == base or name.startswith(f"{base}."):
                try:
                    path.unlink()
                except OSError as exc:
                    deletion_errors.append(f"{name}: {exc}")
        if deletion_errors:
            QMessageBox.warning(
                self,
                "删除并重排",
                "删除文件时出现错误：\n" + "\n".join(deletion_errors[:10]),
            )
            return
        rename_errors: List[str] = []
        suffix_pattern = re.compile(r"^(.*?)(\d+)$")
        for record in self.records[target_idx + 1:]:
            old_base = record.base_name
            if old_base.isdigit():
                new_base = str(int(old_base) - 1).zfill(len(old_base))
            else:
                match = suffix_pattern.match(old_base)
                if not match:
                    rename_errors.append(f"{old_base}: 不支持的命名格式")
                    continue
                prefix, number = match.groups()
                new_base = prefix + str(int(number) - 1).zfill(len(number))
            for path in sorted(folder.iterdir()):
                if not path.is_file():
                    continue
                if path.name == old_base or path.name.startswith(f"{old_base}."):
                    new_name = new_base + path.name[len(old_base):]
                    new_path = path.with_name(new_name)
                    if new_path.exists():
                        rename_errors.append(f"{path.name}: 目标 {new_name} 已存在")
                        continue
                    try:
                        path.rename(new_path)
                    except OSError as exc:
                        rename_errors.append(f"{path.name}: {exc}")
        self.load_directory(self.root_dir)
        if self.records:
            new_index = min(target_idx, len(self.records) - 1)
            self.open_index(new_index)
        if rename_errors:
            QMessageBox.warning(
                self,
                "删除并重排",
                "序号重排已完成，但部分文件未能重命名：\n" + "\n".join(rename_errors[:10]),
            )

    def _lock_or_unlock_all(self, locked: bool) -> None:
        if not self.records:
            QMessageBox.information(self, "批量锁定", "当前没有可操作的文件。")
            return
        if locked and not self.save_current_file(auto=True):
            return
        success = 0
        failures = []
        for record in self.records:
            try:
                set_locked(record.tag_path, locked)
                record.locked = is_locked(record.tag_path)
                success += 1
            except OSError as exc:
                failures.append(f"{record.base_name}: {exc}")
        if self.current_record:
            self.current_locked = is_locked(self.current_record.tag_path)
            self.records[self.current_index].locked = self.current_locked
        self._apply_lock_state()
        self._update_status()
        action = "锁定" if locked else "解锁"
        total = len(self.records)
        message = f"{action}完成：{success}/{total} 个文件已处理。"
        if failures:
            failure_list = "\n".join(failures[:10])
            message += f"\n\n失败文件（最多显示 10 条）：\n{failure_list}"
        QMessageBox.information(self, "批量锁定", message)

    def _show_lock_stats(self) -> None:
        if not self.records:
            QMessageBox.information(self, "锁定统计", "当前没有可操作的文件。")
            return
        locked_files = []
        unlocked_files = []
        for record in self.records:
            record.locked = is_locked(record.tag_path)
            if record.locked:
                locked_files.append(record.base_name)
            else:
                unlocked_files.append(record.base_name)
        locked_count = len(locked_files)
        unlocked_count = len(unlocked_files)
        message_lines = [
            f"已锁定：{locked_count} 个文件\n",
            f"未锁定：{unlocked_count} 个文件\n",
        ]
        if locked_files:
            message_lines.extend([
                "",
                "🔒 已锁定文件：",
                "，".join(locked_files),
            ])
        if unlocked_files:
            message_lines.extend([
                "",
                "🔓 未锁定文件：",
                "，".join(unlocked_files),
            ])
        QMessageBox.information(self, "锁定统计", "".join(message_lines))

    def _export_all_tags(self) -> None:
        if not self.records:
            QMessageBox.information(self, "导出标签", "当前没有可导出的文件。")
            return
        default_dir = str(self.root_dir or Path.cwd())
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择导出文件", default_dir, "JSON 文件 (*.json)"
        )
        if not file_path:
            return
        export_data = {}
        for record in self.records:
            if (
                self.current_record
                and record.tag_path.resolve() == self.current_record.tag_path.resolve()
            ):
                tags = [entry.english for entry in self.current_tags if entry.english.strip()]
            else:
                tags = read_tags(record.tag_path)
            export_data[record.base_name] = tags
        try:
            with open(file_path, "w", encoding="utf-8") as fp:
                json.dump(export_data, fp, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self,
                "导出标签",
                f"已导出 {len(export_data)} 个文件的标签到：\n{file_path}",
            )
        except OSError as exc:
            QMessageBox.warning(self, "导出标签", f"导出失败：{exc}")


    def _export_all_tags_txt(self) -> None:
        if not self.records:
            QMessageBox.information(self, '导出标签（TXT）', '当前没有可导出的文件。')
            return
        default_dir = str(self.root_dir or Path.cwd())
        target_dir = QFileDialog.getExistingDirectory(self, '选择导出文件夹', default_dir)
        if not target_dir:
            return
        target_path = Path(target_dir)
        success = 0
        failures: List[str] = []
        for record in self.records:
            if (
                self.current_record
                and record.tag_path.resolve() == self.current_record.tag_path.resolve()
            ):
                tags = [entry.english for entry in self.current_tags if entry.english.strip()]
            else:
                tags = read_tags(record.tag_path)
            export_file = target_path / f"{record.base_name}.txt"
            try:
                export_file.write_text(', '.join(tags), encoding='utf-8')
                success += 1
            except OSError as exc:
                failures.append(f"{record.base_name}: {exc}")
        message = f'已导出 {success} 个文件到：\n{target_path}'
        if failures:
            failure_list = '\n'.join(failures[:10])
            message += f'\n\n以下文件导出失败（最多显示 10 条）：\n{failure_list}'
        QMessageBox.information(self, '导出标签（TXT）', message)

    def _export_all_images(self) -> None:
        if not self.records:
            QMessageBox.information(self, '导出图片', '当前没有可导出的文件。')
            return
        image_records = [record for record in self.records if record.image_path]
        if not image_records:
            QMessageBox.information(self, '导出图片', '未找到任何图片文件。')
            return
        default_dir = str(self.root_dir or Path.cwd())
        target_dir = QFileDialog.getExistingDirectory(self, '选择导出文件夹', default_dir)
        if not target_dir:
            return
        target_path = Path(target_dir)
        success = 0
        failures: List[str] = []
        missing = 0
        for record in image_records:
            image_path = record.image_path
            if not image_path or not image_path.exists():
                missing += 1
                continue
            destination = target_path / image_path.name
            try:
                shutil.copy2(image_path, destination)
                success += 1
            except OSError as exc:
                failures.append(f"{image_path.name}: {exc}")
        message_lines = [f'已导出 {success} 个图片文件到：', str(target_path)]
        if missing:
            message_lines.append(f'\n缺失图片：{missing} 个（已跳过）')
        if failures:
            failure_list = '\n'.join(failures[:10])
            message_lines.append(f'\n以下图片导出失败（最多显示 10 条）：\n{failure_list}')
        QMessageBox.information(self, '导出图片', ''.join(message_lines))

    def _export_locked_tags(self) -> None:
        locked_records = [
            record for record in self.records if is_locked(record.tag_path)
        ]
        if not locked_records:
            QMessageBox.information(self, "导出已锁定标签", "当前没有已锁定的文件。")
            return
        default_dir = str(self.root_dir or Path.cwd())
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择导出文件", default_dir, "JSON 文件 (*.json)"
        )
        if not file_path:
            return
        export_data = {}
        for record in locked_records:
            if (
                self.current_record
                and record.tag_path.resolve() == self.current_record.tag_path.resolve()
            ):
                tags = [entry.english for entry in self.current_tags if entry.english.strip()]
            else:
                tags = read_tags(record.tag_path)
            export_data[record.base_name] = tags
        try:
            with open(file_path, "w", encoding="utf-8") as fp:
                json.dump(export_data, fp, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self,
                "导出已锁定标签",
                f"已导出 {len(export_data)} 个锁定文件的标签到：\n{file_path}",
            )
        except OSError as exc:
            QMessageBox.warning(self, "导出已锁定标签", f"导出失败：{exc}")

    def bulk_add_tags(self) -> None:
        if not self.records:
            QMessageBox.information(self, "批量添加标签", "当前没有可处理的文件。")
            return
        params = self._prompt_bulk_add()
        if not params:
            return
        tags_to_add, include_locked = params

        success = 0
        already_present = 0
        locked_skipped = 0
        locked_modified = 0
        failures: List[str] = []

        for record in self.records:
            locked = is_locked(record.tag_path)
            if locked and not include_locked:
                locked_skipped += 1
                continue
            try:
                tags = read_tags(record.tag_path)
            except OSError as exc:
                failures.append(f"{record.base_name}: 读取失败（{exc}）")
                continue
            additions = [tag for tag in tags_to_add if tag not in tags]
            if not additions:
                already_present += 1
                continue
            new_tags = tags + additions
            try:
                write_tags(record.tag_path, new_tags)
                record.locked = is_locked(record.tag_path)
                success += 1
                if locked:
                    locked_modified += 1
                if (
                    self.current_record
                    and record.tag_path.resolve() == self.current_record.tag_path.resolve()
                ):
                    self._reload_current_tags(new_tags)
            except OSError as exc:
                failures.append(f"{record.base_name}: 写入失败（{exc}）")

        summary_lines = [
            "批量添加标签完成。",
            f"- 成功更新：{success} 个文件",
            f"- 已包含全部标签：{already_present} 个文件",
        ]
        if include_locked:
            summary_lines.append(f"- 涉及已锁定文件修改：{locked_modified} 个文件")
        else:
            summary_lines.append(f"- 被锁定跳过：{locked_skipped} 个文件")
        summary_lines.append(f"- 写入失败：{len(failures)} 个文件")
        if failures:
            details = "\n".join(failures[:10])
            summary_lines.append(f"\n失败详情（最多显示 10 条）：\n{details}")
        QMessageBox.information(self, "批量添加标签", "\n".join(summary_lines))

    def bulk_replace_tag(self) -> None:
        if not self.records:
            QMessageBox.information(self, "批量替换标签", "当前没有可处理的文件。")
            return
        params = self._prompt_bulk_replace()
        if not params:
            return
        source_tag, target_tag, include_locked = params

        success = 0
        not_found = 0
        locked_skipped = 0
        locked_modified = 0
        failures: List[str] = []

        for record in self.records:
            locked = is_locked(record.tag_path)
            if locked and not include_locked:
                locked_skipped += 1
                continue
            try:
                tags = read_tags(record.tag_path)
            except OSError as exc:
                failures.append(f"{record.base_name}: 读取失败（{exc}）")
                continue
            if source_tag not in tags:
                not_found += 1
                continue
            new_tags = [target_tag if tag == source_tag else tag for tag in tags]
            try:
                write_tags(record.tag_path, new_tags)
                record.locked = is_locked(record.tag_path)
                success += 1
                if locked:
                    locked_modified += 1
                if (
                    self.current_record
                    and record.tag_path.resolve() == self.current_record.tag_path.resolve()
                ):
                    self._reload_current_tags(new_tags)
            except OSError as exc:
                failures.append(f"{record.base_name}: 写入失败（{exc}）")

        summary_lines = [
            f"批量替换标签完成：{source_tag} → {target_tag}",
            f"- 成功更新：{success} 个文件",
            f"- 未找到目标标签：{not_found} 个文件",
        ]
        if include_locked:
            summary_lines.append(f"- 涉及已锁定文件修改：{locked_modified} 个文件")
        else:
            summary_lines.append(f"- 被锁定跳过：{locked_skipped} 个文件")
        summary_lines.append(f"- 写入失败：{len(failures)} 个文件")
        if failures:
            details = "\n".join(failures[:10])
            summary_lines.append(f"\n失败详情（最多显示 10 条）：\n{details}")
        QMessageBox.information(self, "批量替换标签", "\n".join(summary_lines))

    def bulk_delete_tag(self) -> None:
        if not self.records:
            QMessageBox.information(self, "批量删除标签", "当前没有可处理的文件。")
            return
        params = self._prompt_bulk_delete()
        if not params:
            return
        target, include_locked = params

        success = 0
        skipped = 0
        locked_skipped = 0
        locked_modified = 0
        failures: List[str] = []

        for record in self.records:
            locked = is_locked(record.tag_path)
            if locked and not include_locked:
                locked_skipped += 1
                continue
            try:
                tags = read_tags(record.tag_path)
            except OSError as exc:
                failures.append(f"{record.base_name}: 读取失败（{exc}）")
                continue
            if target not in tags:
                skipped += 1
                continue
            new_tags = [tag for tag in tags if tag != target]
            try:
                write_tags(record.tag_path, new_tags)
                record.locked = is_locked(record.tag_path)
                success += 1
                if locked:
                    locked_modified += 1
                if (
                    self.current_record
                    and record.tag_path.resolve() == self.current_record.tag_path.resolve()
                ):
                    self._reload_current_tags(new_tags)
            except OSError as exc:
                failures.append(f"{record.base_name}: 写入失败（{exc}）")

        summary_lines = [
            f"删除标签“{target}”完成。",
            f"- 成功更新：{success} 个文件",
            f"- 未找到该标签：{skipped} 个文件",
        ]
        if include_locked:
            summary_lines.append(f"- 涉及已锁定文件修改：{locked_modified} 个文件")
        else:
            summary_lines.append(f"- 被锁定跳过：{locked_skipped} 个文件")
        summary_lines.append(f"- 写入失败：{len(failures)} 个文件")
        if failures:
            details = "\n".join(failures[:10])
            summary_lines.append(f"\n失败详情（最多显示 10 条）：\n{details}")
        QMessageBox.information(self, "批量删除标签", "\n".join(summary_lines))

    def open_index(self, index: int) -> None:
        if index < 0 or index >= len(self.records):
            return
        if not self.ensure_saved():
            return
        self.current_index = index
        self.current_record = self.records[index]
        record = self.current_record
        self.current_locked = record.locked or is_locked(record.tag_path)
        self.viewer.load_image(str(record.image_path) if record.image_path else None)
        english = read_tags(record.tag_path)
        self.initial_tags = english[:]
        translations = self.translator.translate_many(english, "en", "zh")
        self.current_tags = [TagEntry(i + 1, en, zh) for i, (en, zh) in enumerate(zip(english, translations))]
        self._id_counter = itertools.count(len(self.current_tags) + 1)
        self.undo_stack.clear(); self.undo_stack.setClean()
        self.refresh_lists()

    def open_next_unlocked(self) -> None:
        if not self.records:
            QMessageBox.information(self, "下一个未锁定", "当前没有可用的文件。")
            return
        start = 0 if self.current_index is None else self.current_index + 1
        for idx in range(start, len(self.records)):
            record = self.records[idx]
            record.locked = is_locked(record.tag_path)
            if not record.locked:
                self.open_index(idx)
                return
        QMessageBox.information(self, "下一个未锁定", "后续没有未锁定的文件。")

    def next_entry_id(self) -> int:
        return next(self._id_counter)

    def apply_entry(self, entry_id: int, english: str, chinese: str) -> None:
        for entry in self.current_tags:
            if entry.entry_id == entry_id:
                entry.english = english; entry.chinese = chinese; break
        self.refresh_lists()

    def insert_entry(self, entry: TagEntry, index: Optional[int] = None, keep_id: bool = False) -> None:
        if not keep_id:
            entry.entry_id = self.next_entry_id()
        if index is None:
            self.current_tags.append(entry)
        else:
            self.current_tags.insert(index, entry)
        self.refresh_lists()

    def remove_entry(self, entry_id: int) -> None:
        self.current_tags = [item for item in self.current_tags if item.entry_id != entry_id]
        self.refresh_lists()

    def _handle_edit(self, entry_id: int, field: str, old: str, new: str) -> None:
        if self.current_locked:
            self._editing_locked_warning()
            return
        new_text, old_text = normalize(new), normalize(old)
        if new_text == old_text:
            return
        entry = next((item for item in self.current_tags if item.entry_id == entry_id), None)
        if not entry:
            return
        if field == "english":
            if not self._can_accept_new_tag(new_text, exclude_entry_id=entry_id):
                self.statusBar().showMessage('标签已存在（包含复数形式），修改被忽略。', 3000)
                return
            chinese = self.translator.translate_one(new_text, "en", "zh")
            cmd = ModifyTagCommand(self, entry_id, entry.english, entry.chinese, new_text, chinese)
        else:
            english = self.translator.translate_one(new_text, "zh", "en")
            if not self._can_accept_new_tag(english, exclude_entry_id=entry_id):
                self.statusBar().showMessage('标签已存在（包含复数形式），修改被忽略。', 3000)
                return
            cmd = ModifyTagCommand(self, entry_id, entry.english, entry.chinese, english, new_text)
        self.undo_stack.push(cmd)

    def _handle_delete(self, entry_id: int) -> None:
        if self.current_locked:
            self._editing_locked_warning()
            return
        for idx, entry in enumerate(self.current_tags):
            if entry.entry_id == entry_id:
                self.undo_stack.push(RemoveTagCommand(self, entry, idx))
                break

    def _handle_add(self) -> None:
        if self.current_locked:
            self._editing_locked_warning()
            return
        text, ok = QInputDialog.getText(self, "添加标签", "请输入标签（支持中文或英文）：")
        if not ok:
            return
        cleaned = normalize(text)
        if cleaned:
            self.undo_stack.push(AddTagCommand(self, cleaned))

    def _handle_retranslate(self) -> None:
        if self.current_locked:
            self._editing_locked_warning()
            return
        if not self.current_tags:
            return
        english = [entry.english for entry in self.current_tags]
        translations = self.translator.translate_many(english, "en", "zh")
        for entry, zh in zip(self.current_tags, translations):
            entry.chinese = zh
        self.refresh_lists()
        self.statusBar().showMessage("已重新翻译。", 3000)

    def restore_initial(self) -> None:
        if self.current_locked:
            self._editing_locked_warning()
            return
        if not self.initial_tags:
            return
        translations = self.translator.translate_many(self.initial_tags, "en", "zh")
        self.current_tags = [TagEntry(i + 1, en, zh) for i, (en, zh) in enumerate(zip(self.initial_tags, translations))]
        self._id_counter = itertools.count(len(self.current_tags) + 1)
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self.refresh_lists()
        self.statusBar().showMessage("已恢复初始状态。", 3000)

    def refresh_lists(self) -> None:
        self._populate_tag_widgets()
        self._apply_lock_state()
        self._update_status()

    def _update_status(self) -> None:
        if self.current_index is None or not self.records:
            self.file_label.setText("当前文件：无")
            self.statusBar().showMessage("未加载文件")
            return
        record = self.records[self.current_index]
        prefix = "* " if not self.undo_stack.isClean() else ""
        tag_name = record.tag_path.name if record.tag_path else "无标签文件"
        state_text = "🔒 已锁定" if self.current_locked else "可编辑"
        self.file_label.setText(f"当前文件：{tag_name}（{state_text}）")
        message = (
            f"{prefix}{record.base_name} ({self.current_index + 1}/{len(self.records)}) | "
            f"标签 {len(self.current_tags)} | 缩放 {self.viewer.zoom_percent()}% | "
            f"翻译链 {self.translator.describe_pipeline('en', 'zh')} | "
            f"后缀 {self.tag_suffix} | 状态 {state_text}"
        )
        self.statusBar().showMessage(message)

    def ensure_saved(self) -> bool:
        return True if self.undo_stack.isClean() else self.save_current_file(auto=True)

    def save_current_file(self, auto: bool = False) -> bool:
        if not self.current_record:
            return True
        tags = [entry.english for entry in self.current_tags if entry.english.strip()]
        try:
            write_tags(self.current_record.tag_path, tags)
            self.undo_stack.setClean()
            self.statusBar().showMessage("保存成功。", 3000)
            return True
        except OSError as exc:
            if not auto:
                QMessageBox.warning(self, "保存失败", str(exc))
            return False

    def _on_clean_changed(self, clean: bool) -> None:
        title = "标签校准工具"
        if self.current_record:
            title += f" - {self.current_record.base_name}"
        if not clean:
            title = "* " + title
        self.setWindowTitle(title)
        self._update_status()

    def open_next(self) -> None:
        if not self.records:
            return
        if self.current_index is None:
            self.open_index(0)
            return
        if self.current_index >= len(self.records) - 1:
            QMessageBox.information(self, "提示", "已经是最后一个文件。")
            return
        self.open_index(self.current_index + 1)

    def open_previous(self) -> None:
        if not self.records:
            return
        if self.current_index is None:
            self.open_index(0)
            return
        if self.current_index <= 0:
            QMessageBox.information(self, "提示", "已经是第一个文件。")
            return
        self.open_index(self.current_index - 1)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Right and not event.modifiers():
            self.open_next(); return
        if event.key() == Qt.Key_Left and not event.modifiers():
            self.open_previous(); return
        super().keyPressEvent(event)

    def open_tag_file(self) -> None:
        start = str(self.root_dir or DEFAULT_DIRECTORY)
        path, _ = QFileDialog.getOpenFileName(self, "选择标签文件", start, "文本文件 (*.txt);;所有文件 (*)")
        if path:
            target = Path(path); self.load_directory(target.parent, target)

    def set_tag_suffix(self) -> None:
        suffix, ok = QInputDialog.getText(self, "设置标签后缀", "请输入后缀：", text=self.tag_suffix)
        if ok:
            suffix = suffix.strip()
            if suffix and not suffix.startswith("."):
                suffix = "." + suffix
            if suffix:
                self.tag_suffix = suffix
                if self.root_dir:
                    self.load_directory(self.root_dir)

