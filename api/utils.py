# api/utils.py
import re, unicodedata
def normalize_name(x: str | None) -> str:
    if not x:
        return ""
    x = str(x).lower().strip()
    x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()
    x = re.sub(r"\(.*?\)", "", x)
    x = x.replace("-", " ").replace("_", " ")
    x = re.sub(r"[^a-z0-9 ]", "", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def color_scale(value: float) -> str:
    """Simple color scale for choropleth."""
    if value is None:
        return "#cccccc"
    if value < 5:
        return "#a1dab4"
    elif value < 15:
        return "#41b6c4"
    elif value < 30:
        return "#2c7fb8"
    else:
        return "#253494"
