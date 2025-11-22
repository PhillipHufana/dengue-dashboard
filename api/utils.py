# api/utils.py

def normalize_name(name: str) -> str:
    """Standardize barangay names for lookup."""
    return name.strip().lower().replace("-", " ").replace("_", " ")


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
