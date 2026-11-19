"""Verbatim extracted WBS pure functions; no story text regeneration."""
import re
import hashlib
import json

def count_words(text):
    return len(re.findall(r"\b\w+\b", str(text or "")))


def get_text_signature(text):
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def safe_download_stem(value, fallback="writersblock_output"):
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return stem.lower() or fallback


