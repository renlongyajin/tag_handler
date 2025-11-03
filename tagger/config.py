from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
DEFAULT_TAG_SUFFIX = ".final.txt"
DEFAULT_DIRECTORY = Path("data/poren")
DICTIONARY_PATH = Path("data/local_dictionary.json")
LIBRE_TRANSLATE_ENDPOINT = "https://libretranslate.de/translate"
LOCK_SUFFIX = ".lock"


def ensure_dictionary_file(path: Path = DICTIONARY_PATH) -> Dict[str, str]:
    path = path
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{}", encoding="utf-8")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        path.write_text("{}", encoding="utf-8")
        return {}
    return data if isinstance(data, dict) else {}
