# import json, pandas as pd

# from pathlib import Path
# import json

# BASE = Path(__file__).resolve().parent  # the /data folder
# geo_path = BASE / "DAVAO_Poly_geo.geojson"

# with geo_path.open("r", encoding="utf-8") as f:
#     data = json.load(f)

# print("Loaded:", geo_path)


# names = []
# for feat in data["features"]:
#     props = feat.get("properties", {})
#     n = (
#         props.get("name")
#         or props.get("NAME")
#         or props.get("Barangay")
#         or props.get("BARANGAY")
#         or props.get("BRGY_NAME")
#     )
#     names.append(n)

# print(pd.Series(names).unique())
# import json
# from pathlib import Path

# path = Path("data/DAVAO_Poly_geo.geojson")

# with path.open("r", encoding="utf-8") as f:
#     geo = json.load(f)

# for i, feat in enumerate(geo.get("features", [])):
#     print("Feature", i)
#     print(list(feat.get("properties", {}).keys()))
#     if i == 4:
#         break


# import pandas as pd

# df = pd.read_csv("intermediate/weekly_cases_all_barangays.csv")

# print(df["Barangay_standardized"].unique())

import json

geo = json.load(open("data/DAVAO_Poly_geo.geojson"))
names = [x["properties"]["ADM4_EN"] for x in geo["features"]]
print(sorted(set(names)))
