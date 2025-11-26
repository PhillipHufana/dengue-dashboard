import unicodedata
import re

def normalize_barangay_name(x: str | None) -> str:
    """Universal normalization used by pipeline + Supabase + API + map."""
    if not x:
        return ""

    x = str(x).strip().lower()
    x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()
    x = re.sub(r"\(.*?\)", "", x)
    x = x.replace("-", " ")
    x = re.sub(r"[^a-z0-9 ]", "", x)
    x = re.sub(r"\s+", " ", x).strip()

    return x

# Backwards compatible alias (required by export_supabase.py)
def normalize_name(x: str | None) -> str:
    return normalize_barangay_name(x)
