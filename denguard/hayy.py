import pandas as pd

df = pd.read_csv("intermediate/dengue_cleaned.csv", dtype={"CASE ID":"string"}, low_memory=False)
df["date_onset"] = pd.to_datetime(df["DOnset"], errors="coerce")
df_ok = df.dropna(subset=["date_onset", "Barangay_key"])
df_ok = df_ok[df_ok["date_onset"].between("2017-01-01", "2025-12-31")]

w = pd.read_csv("intermediate/weekly_cases_all_barangays.csv")
print("Case rows used:", len(df_ok))
print("Weekly sum:", int(w["Cases"].sum()))
