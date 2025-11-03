from __future__ import annotations


def normalize(text: str) -> str:
    return text.strip()


def detect_language(text: str) -> str:
    """粗略检测输入是否包含中文字符，用于判断标签语言"""
    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            return "zh"
    return "en"
