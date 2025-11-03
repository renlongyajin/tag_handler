from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FileRecord:
    base_name: str
    image_path: Optional[Path]
    tag_path: Path
    locked: bool = False


@dataclass
class TagEntry:
    entry_id: int
    english: str
    chinese: str
