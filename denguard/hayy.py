import pandas as pd

loc = pd.read_csv("intermediate/barangay_local_forecasts_long.csv")
dis = pd.read_csv("intermediate/barangay_forecasts_all_models_future_long.csv")

loc_keys = set(loc["Barangay_key"].unique())
dis_keys = set(dis["Barangay_key"].unique())

print("loc keys not in all_models:", len(loc_keys - dis_keys))
print("sample:", list(loc_keys - dis_keys)[:20])
