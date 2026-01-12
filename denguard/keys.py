from __future__ import annotations

import re
import unicodedata
import pandas as pd

def _fix_mojibake(s: str) -> str:
    """
    Try to repair common bad encodings like 'PequeÃ±o' -> 'Pequeño'.
    If it fails, return the original.
    """
    try:
        return s.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

def make_barangay_db_key(s: object) -> str:
    if s is None or pd.isna(s):
        return ""

    s = str(s).strip()

    # 1) Repair mojibake before lowercasing/normalizing
    s = _fix_mojibake(s)

    # 2) Lowercase
    s = s.lower()

    # 3) Normalize unicode and strip accents (ñ -> n)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))

    # 4) Remove '(pob.)' and any parentheses content (matches your DB 'name')
    s = re.sub(r"\s*\(pob\.?\)", "", s)
    s = re.sub(r"\s*\(.*?\)", "", s)

    # 5) Remove punctuation / non-alphanumerics
    s = re.sub(r"[.,\-]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)

    # 6) Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s
