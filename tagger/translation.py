from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import requests

from .config import LIBRE_TRANSLATE_ENDPOINT, ensure_dictionary_file, DICTIONARY_PATH

CacheKey = Tuple[str, str, str]


class BaseTranslator:
    name = "base"

    @property
    def available(self) -> bool:
        return True

    def translate(self, text: str, source: str, target: str) -> Optional[str]:
        raise NotImplementedError

    def translate_many(
        self, texts: Iterable[str], source: str, target: str
    ) -> List[Optional[str]]:
        return [self.translate(text, source, target) for text in texts]


class GoogleTranslateTranslator(BaseTranslator):
    name = "Google"
    _endpoint = "https://translate.googleapis.com/translate_a/single"

    def __init__(self) -> None:
        self.session = requests.Session()

    def translate(self, text: str, source: str, target: str) -> Optional[str]:
        if not text.strip():
            return ""
        params = {
            "client": "gtx",
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": text,
        }
        try:
            resp = self.session.get(self._endpoint, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None
        try:
            return "".join(part[0] for part in data[0]).strip()
        except Exception:
            return None


class LibreTranslateTranslator(BaseTranslator):
    name = "LibreTranslate"

    def __init__(self, endpoint: str = LIBRE_TRANSLATE_ENDPOINT) -> None:
        self.endpoint = endpoint
        self.session = requests.Session()
        self.headers = {"Accept": "application/json"}

    def translate_many(
        self, texts: Iterable[str], source: str, target: str
    ) -> List[Optional[str]]:
        items = list(texts)
        if not items:
            return []
        payload = {"q": items, "source": source, "target": target, "format": "text"}
        try:
            resp = self.session.post(
                self.endpoint, json=payload, headers=self.headers, timeout=8
            )
            resp.raise_for_status()
            translated = resp.json().get("translatedText", "")
        except Exception:
            return [None for _ in items]
        if isinstance(translated, list):
            parts = translated
        elif isinstance(translated, str):
            parts = translated.split("\n")
        else:
            parts = []
        if len(parts) != len(items):
            return [self.translate(text, source, target) for text in items]
        return [str(part).strip() for part in parts]

    def translate(self, text: str, source: str, target: str) -> Optional[str]:
        payload = {"q": text, "source": source, "target": target, "format": "text"}
        try:
            resp = self.session.post(
                self.endpoint, json=payload, headers=self.headers, timeout=8
            )
            resp.raise_for_status()
            translated = resp.json().get("translatedText", "")
            return translated.strip() if isinstance(translated, str) else str(translated)
        except Exception:
            return None


class ArgosTranslateTranslator(BaseTranslator):
    name = "Argos"

    def __init__(self) -> None:
        try:
            from argostranslate import translate

            self._translate = translate
            self._languages = translate.get_installed_languages()
        except Exception:
            self._translate = None
            self._languages = []

    @property
    def available(self) -> bool:
        return bool(self._translate and self._languages)

    def _get_translation(self, source: str, target: str):
        if not self.available:
            return None
        source_lang = next((lang for lang in self._languages if lang.code == source), None)
        target_lang = next((lang for lang in self._languages if lang.code == target), None)
        if not source_lang or not target_lang:
            return None
        return source_lang.get_translation(target_lang)

    def translate(self, text: str, source: str, target: str) -> Optional[str]:
        bridge = self._get_translation(source, target)
        if not bridge:
            return None
        try:
            return bridge.translate(text).strip()
        except Exception:
            return None


class DictionaryTranslator(BaseTranslator):
    name = "Dictionary"

    def __init__(self, mapping: Dict[str, str]) -> None:
        self.mapping = mapping
        self.reverse = {value: key for key, value in mapping.items()}

    def translate(self, text: str, source: str, target: str) -> Optional[str]:
        cleaned = text.strip()
        if not cleaned:
            return ""
        if source.startswith("en") and target.startswith("zh"):
            return self.mapping.get(cleaned)
        if source.startswith("zh") and target.startswith("en"):
            return self.reverse.get(cleaned)
        return None


class TranslationManager:
    def __init__(self) -> None:
        dictionary = ensure_dictionary_file(DICTIONARY_PATH)
        self.cache: Dict[CacheKey, str] = {}
        google = GoogleTranslateTranslator()
        libre = LibreTranslateTranslator()
        argos = ArgosTranslateTranslator()
        dictionary_translator = DictionaryTranslator(dictionary)
        self.en_to_zh = [
            google,
            libre,
            argos,
            dictionary_translator,
        ]
        self.zh_to_en = [
            google,
            libre,
            ArgosTranslateTranslator(),
            dictionary_translator,
        ]

    def _pipeline(self, source: str, target: str) -> List[BaseTranslator]:
        if source.startswith("en") and target.startswith("zh"):
            return [tran for tran in self.en_to_zh if tran.available]
        if source.startswith("zh") and target.startswith("en"):
            return [tran for tran in self.zh_to_en if tran.available]
        return []

    def translate_many(self, texts: List[str], source: str, target: str) -> List[str]:
        results: List[Optional[str]] = [None] * len(texts)
        pending = []
        for idx, text in enumerate(texts):
            trimmed = text.strip()
            key = (source, target, trimmed)
            if not trimmed:
                results[idx] = ""
            elif key in self.cache:
                results[idx] = self.cache[key]
            else:
                pending.append(idx)

        pipeline = self._pipeline(source, target)
        while pending and pipeline:
            translator = pipeline.pop(0)
            subset = [texts[i] for i in pending]
            outputs = translator.translate_many(subset, source, target)
            next_pending: List[int] = []
            for idx, out in zip(pending, outputs):
                trimmed = texts[idx].strip()
                key = (source, target, trimmed)
                if out and out.strip():
                    cleaned = out.strip()
                    self.cache[key] = cleaned
                    results[idx] = cleaned
                else:
                    next_pending.append(idx)
            pending = next_pending

        for idx, text in enumerate(texts):
            if results[idx] is None:
                trimmed = text.strip()
                self.cache[(source, target, trimmed)] = trimmed
                results[idx] = trimmed
        return [value or "" for value in results]

    def translate_one(self, text: str, source: str, target: str) -> str:
        trimmed = text.strip()
        key = (source, target, trimmed)
        if key in self.cache:
            return self.cache[key]
        result = self.translate_many([text], source, target)[0]
        self.cache[key] = result
        return result

    def describe_pipeline(self, source: str, target: str) -> str:
        chain = self._pipeline(source, target)
        return " -> ".join(tr.name for tr in chain) if chain else "无可用翻译"
