import json
import pandas as pd
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
poly_path = BASE / "DAVAO_Poly_geo.geojson"
csv_path = BASE / "weekly_cases_all_barangays.csv"     # update if needed

# ----------------------------
# Normalization function
# ----------------------------
def normalize(x: str | None):
    if not x:
        return ""
    x = x.lower()
    x = re.sub(r"\(.*?\)", "", x)       # remove (Pob.), etc
    x = x.replace("-", " ")
    x = re.sub(r"\s+", " ", x)
    x = re.sub(r"[^\w\s]", "", x)       # remove punctuation
    return x.strip()

# ----------------------------
# Load polygon barangay names
# ----------------------------
with open(poly_path, "r", encoding="utf-8") as f:
    gj = json.load(f)

poly_raw = []
poly_norm = []

for feat in gj["features"]:
    props = feat.get("properties", {})
    name = props.get("ADM4_EN") or props.get("ADM4_REF") or ""
    poly_raw.append(name)
    poly_norm.append(normalize(name))

poly_df = pd.DataFrame({"raw": poly_raw, "normalized": poly_norm})

# ----------------------------
# Load your barangay dataset
# ----------------------------
df = pd.read_csv(csv_path)

# column must match your Supabase normalized name
if "Barangay_key" in df.columns:
    csv_norm = df["Barangay_key"].astype(str).apply(normalize)
elif "name" in df.columns:
    csv_norm = df["name"].astype(str).apply(normalize)
else:
    raise ValueError("CSV must contain 'Barangay_key' or 'name' column")

csv_df = pd.DataFrame({
    "raw": df.iloc[:,0],
    "normalized": csv_norm
})

# ----------------------------
# Compare both sets
# ----------------------------
set_poly = set(poly_norm)
set_csv = set(csv_norm)

intersect = sorted(set_poly & set_csv)
missing_in_polygon = sorted(set_csv - set_poly)
missing_in_csv = sorted(set_poly - set_csv)

# ----------------------------
# Print Report
# ----------------------------
print("\n==============================")
print(" RECONCILIATION REPORT")
print("==============================")

print(f"\nTotal polygon names: {len(set_poly)}")
print(f"Total CSV names:     {len(set_csv)}")
print(f"Matches:             {len(intersect)}")

print("\n--- Missing in POLYGONS (exists in CSV but polygon name mismatch) ---")
for n in missing_in_polygon:
    print("  •", n)

print("\n--- Missing in CSV (exists in polygon but not in dengue data) ---")
for n in missing_in_csv:
    print("  •", n)

print("\n==============================")
print(" Done. Review mismatches above.")
print("==============================\n")
