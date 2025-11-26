# tools/check_reconciliation.py
from pathlib import Path
import json
import pandas as pd

from denguard.normalize import normalize_barangay_name

# ---------------------------------------------------------
# CONFIG — UPDATE PATHS IF NEEDED
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INTERMEDIATE = ROOT / "intermediate"

GEO_PATH = DATA_DIR / "DAVAO_Poly_geo.geojson"
CSV_PATH = INTERMEDIATE / "weekly_cases_all_barangays.csv"


def load_polygon_names():
    """Load ADM4_EN names from polygons + normalize."""
    with GEO_PATH.open("r", encoding="utf-8") as f:
        geo = json.load(f)

    names = []
    for feat in geo["features"]:
        props = feat.get("properties", {})
        raw = props.get("ADM4_EN") or ""
        names.append(normalize_barangay_name(raw))

    return names


def load_csv_names():
    """Load Barangay_standardized from weekly_cases CSV + normalize."""
    df = pd.read_csv(CSV_PATH)

    if "Barangay_standardized" not in df.columns:
        raise KeyError("CSV missing Barangay_standardized column.")

    names = df["Barangay_standardized"].dropna().astype(str)

    normed = [normalize_barangay_name(n) for n in names]

    return normed


def main():
    print("\n==============================")
    print("   RECONCILIATION REPORT")
    print("==============================")

    # Load lists
    poly = load_polygon_names()
    csv_names = load_csv_names()

    poly_set = set(poly)
    csv_set = set(csv_names)

    print(f"\nPolygon barangays:   {len(poly_set)}")
    print(f"Dengue barangays:    {len(csv_set)}")

    # Differences
    missing_in_polygons = sorted(csv_set - poly_set)
    missing_in_csv = sorted(poly_set - csv_set)

    print("\n--- Missing in POLYGONS (exists in CSV but not in polygons) ---")
    if missing_in_polygons:
        for x in missing_in_polygons:
            print(f"  • {x}")
    else:
        print("  ✔ None")

    print("\n--- Missing in CSV (exists in polygons but not in dengue data) ---")
    if missing_in_csv:
        for x in missing_in_csv:
            print(f"  • {x}")
    else:
        print("  ✔ None")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
