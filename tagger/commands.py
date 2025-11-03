from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING

from PyQt5.QtWidgets import QUndoCommand

from .dto import TagEntry
from .utils import detect_language

if TYPE_CHECKING:
    from .main_window import TagEditorMainWindow


class ModifyTagCommand(QUndoCommand):
    def __init__(
        self,
        window: "TagEditorMainWindow",
        entry_id: int,
        old_en: str,
        old_zh: str,
        new_en: str,
        new_zh: str,
    ) -> None:
        super().__init__("修改标签")
        self.window = window
        self.entry_id = entry_id
        self.old_en = old_en
        self.old_zh = old_zh
        self.new_en = new_en
        self.new_zh = new_zh

    def undo(self) -> None:
        self.window.apply_entry(self.entry_id, self.old_en, self.old_zh)

    def redo(self) -> None:
        self.window.apply_entry(self.entry_id, self.new_en, self.new_zh)


class AddTagCommand(QUndoCommand):
    def __init__(self, window: "TagEditorMainWindow", raw_text: str) -> None:
        super().__init__("添加标签")
        self.window = window
        self.raw_text = raw_text
        self.entry: Optional[TagEntry] = None

    def redo(self) -> None:
        if not self.entry:
            detected = detect_language(self.raw_text)
            if detected == "zh":
                chinese = self.raw_text.strip()
                english = self.window.translator.translate_one(self.raw_text, "zh", "en").strip()
                if not english:
                    english = chinese
            else:
                english = self.raw_text.strip()
                chinese = self.window.translator.translate_one(self.raw_text, "en", "zh").strip()
                if not chinese:
                    chinese = english
            english = english.strip()
            chinese = chinese.strip()
            entry_id = self.window.next_entry_id()
            self.entry = TagEntry(entry_id, english, chinese)
        self.window.insert_entry(self.entry)

    def undo(self) -> None:
        if self.entry:
            self.window.remove_entry(self.entry.entry_id)


class RemoveTagCommand(QUndoCommand):
    def __init__(self, window: "TagEditorMainWindow", entry: TagEntry, index: int) -> None:
        super().__init__("删除标签")
        self.window = window
        self.entry = TagEntry(entry.entry_id, entry.english, entry.chinese)
        self.index = index

    def redo(self) -> None:
        self.window.remove_entry(self.entry.entry_id)

    def undo(self) -> None:
        self.window.insert_entry(self.entry, self.index, keep_id=True)


class ReplaceAllTagsCommand(QUndoCommand):
    def __init__(self, window: "TagEditorMainWindow", new_pairs: List[Tuple[str, str]]) -> None:
        super().__init__("替换全部标签")
        self.window = window
        self.new_pairs = [(english, chinese) for english, chinese in new_pairs]
        self.old_pairs = [
            (entry.english, entry.chinese) for entry in window.current_tags
        ]

    def redo(self) -> None:
        self.window._apply_entry_pairs(self.new_pairs)

    def undo(self) -> None:
        self.window._apply_entry_pairs(self.old_pairs)
