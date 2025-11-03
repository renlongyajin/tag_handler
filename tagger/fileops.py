from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .config import IMAGE_EXTENSIONS, DEFAULT_TAG_SUFFIX, LOCK_SUFFIX
from .dto import FileRecord


def discover_records(folder: Path, tag_suffix: str = DEFAULT_TAG_SUFFIX) -> List[FileRecord]:
    files: Dict[str, FileRecord] = {}
    for entry in folder.iterdir():
        if not entry.is_file():
            continue
        stem = entry.stem
        suffix = entry.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            record = files.get(stem)
            if record:
                record.image_path = entry
            else:
                lock_path = _lock_path(folder / f"{stem}{tag_suffix}")
                locked = lock_path.exists()
                files[stem] = FileRecord(stem, entry, folder / f"{stem}{tag_suffix}", locked)
        elif entry.name.endswith(tag_suffix):
            stem = entry.name[: -len(tag_suffix)]
            record = files.get(stem)
            image_path = record.image_path if record else _find_image(folder, stem)
            lock_path = _lock_path(entry)
            locked = lock_path.exists()
            files[stem] = FileRecord(stem, image_path, entry, locked)
    for stem, record in list(files.items()):
        if not record.tag_path:
            record.tag_path = folder / f"{stem}{tag_suffix}"
        record.locked = _lock_path(record.tag_path).exists()
    return sorted(files.values(), key=lambda rec: rec.base_name)


def _find_image(folder: Path, stem: str) -> Optional[Path]:
    for suffix in IMAGE_EXTENSIONS:
        candidate = folder / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def read_tags(path: Path) -> List[str]:
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    parts = content.replace("\n", ",").split(",")
    return [piece.strip() for piece in parts if piece.strip()]


def write_tags(path: Path, tags: List[str]) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_suffix(path.suffix + ".bak")
    if path.exists() and not backup.exists():
        try:
            shutil.copy2(path, backup)
        except OSError:
            pass
    content = ", ".join(tag.strip() for tag in tags if tag.strip())
    path.write_text(content, encoding="utf-8")


def _lock_path(tag_path: Path) -> Path:
    return Path(str(tag_path) + LOCK_SUFFIX)


def is_locked(tag_path: Path) -> bool:
    return _lock_path(tag_path).exists()


def set_locked(tag_path: Path, locked: bool) -> None:
    lock_path = _lock_path(tag_path)
    if locked:
        if not lock_path.exists():
            lock_path.touch()
    else:
        if lock_path.exists():
            lock_path.unlink()
