import os
import numpy as np
import pandas as pd

OUT = "intermediate"

# 1) pick a forecasts-long file that contains horizon_type==test
candidates = [
    os.path.join(OUT, "barangay_forecasts_long.csv"),
    os.path.join(OUT, "barangay_forecasts_all_models_long.csv"),
    os.path.join(OUT, "barangay_forecasts.csv"),
    os.path.join(OUT, "barangay_local_forecasts_long.csv"),
]
path = next((p for p in candidates if os.path.exists(p)), None)
if path is None:
    raise SystemExit("No forecast file found in intermediate/. Looked for: " + ", ".join(candidates))

df = pd.read_csv(path)
if "horizon_type" not in df.columns:
    raise SystemExit(f"{path} has no horizon_type column, can't isolate test horizon.")

# Expect long columns: Barangay_key, ds, model_name, yhat, horizon_type
need = {"Barangay_key","ds","model_name","yhat","horizon_type"}
missing = need - set(df.columns)
if missing:
    raise SystemExit(f"{path} missing columns: {missing}")

df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
df = df.dropna(subset=["ds"])

test_pred = df[df["horizon_type"].astype(str).str.lower().eq("test")].copy()
if test_pred.empty:
    raise SystemExit(f"{path} has no rows with horizon_type=='test'.")

# 2) load actuals
actual_path = os.path.join(OUT, "barangay_weekly.csv")
if not os.path.exists(actual_path):
    raise SystemExit("Missing intermediate/barangay_weekly.csv (actuals).")

act = pd.read_csv(actual_path)
# try common column names
if "WeekStart" in act.columns:
    act = act.rename(columns={"WeekStart":"ds"})
if "Cases" in act.columns:
    act = act.rename(columns={"Cases":"y"})
need_act = {"Barangay_key","ds","y"}
missing_act = need_act - set(act.columns)
if missing_act:
    raise SystemExit(f"{actual_path} missing columns: {missing_act}")

act["ds"] = pd.to_datetime(act["ds"], errors="coerce")
act["y"] = pd.to_numeric(act["y"], errors="coerce").fillna(0.0)
act = act.dropna(subset=["ds"]).groupby(["Barangay_key","ds"], as_index=False)["y"].sum()

# 3) join
m = test_pred.merge(act, on=["Barangay_key","ds"], how="left")
m["y"] = m["y"].fillna(0.0)
m["yhat"] = pd.to_numeric(m["yhat"], errors="coerce").fillna(0.0)

# 4) metrics
def smape(y, yhat, eps=1e-8):
    denom = np.abs(y) + np.abs(yhat) + eps
    return float(np.mean(2.0*np.abs(yhat-y)/denom))

def rmse(y, yhat):
    return float(np.sqrt(np.mean((yhat-y)**2)))

def mae(y, yhat):
    return float(np.mean(np.abs(yhat-y)))

rows = []
for model, g in m.groupby("model_name"):
    y = g["y"].to_numpy(float)
    yhat = g["yhat"].to_numpy(float)
    rows.append({
        "model_name": model,
        "n_rows": len(g),
        "RMSE": rmse(y, yhat),
        "MAE": mae(y, yhat),
        "sMAPE": smape(y, yhat),
    })

out = pd.DataFrame(rows).sort_values("model_name")
print("\n== TEST METRICS (all barangay-weeks) ==")
print(out.to_string(index=False))

# 5) Optional: metrics only for the chosen model per barangay (preferred selection logic)
perf_path = os.path.join(OUT, "local_model_performance.csv")
if os.path.exists(perf_path):
    perf = pd.read_csv(perf_path, usecols=["Barangay_key","Chosen"])
    mm = m.merge(perf, on="Barangay_key", how="left")
    chosen_only = mm[mm["model_name"].astype(str).eq(mm["Chosen"].astype(str))].copy()
    if not chosen_only.empty:
        rows2 = []
        for model, g in chosen_only.groupby("model_name"):
            y = g["y"].to_numpy(float)
            yhat = g["yhat"].to_numpy(float)
            rows2.append({
                "model_name": model,
                "n_rows": len(g),
                "RMSE": rmse(y, yhat),
                "MAE": mae(y, yhat),
                "sMAPE": smape(y, yhat),
            })
        out2 = pd.DataFrame(rows2).sort_values("model_name")
        print("\n== TEST METRICS (ONLY where model_name == Chosen for that barangay) ==")
        print(out2.to_string(index=False))
