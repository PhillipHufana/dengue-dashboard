from __future__ import annotations
import numpy as np
import pandas as pd
from denguard.config import Config

def reconcile_forecasts(
    hybrid_bg_forecast: pd.DataFrame,
    local_forecasts_all: pd.DataFrame,
    chosen_city_forecast: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    print("\n== STEP 19: Forecast Reconciliation (Corrected) ==")

    city = chosen_city_forecast.copy()
    city["ds"] = pd.to_datetime(city["ds"])
    if "CityForecast" in city.columns:
        city = city[["ds", "CityForecast"]]
    elif "yhat" in city.columns:
        city = city[["ds", "yhat"]].rename(columns={"yhat": "CityForecast"})
    else:
        raise KeyError("No city forecast column found. Expecting 'CityForecast' or 'yhat'.")
    city = city.sort_values("ds").reset_index(drop=True)

    hyb = hybrid_bg_forecast.copy()
    hyb["ds"] = pd.to_datetime(hyb["ds"])
    hyb["Forecast"] = pd.to_numeric(hyb["Forecast"], errors="coerce").fillna(0.0)
    hyb["Forecast"] = hyb["Forecast"].clip(lower=0)

    loc = local_forecasts_all.copy()
    loc["ds"] = pd.to_datetime(loc["ds"])
    loc["local_forecast"] = (
        pd.to_numeric(loc["local_forecast"], errors="coerce").fillna(0.0).clip(lower=0)
    )

    merged = hyb.merge(
        loc,
        on=["Barangay_standardized", "ds"],
        how="left",
    )

    merged["Final"] = merged["local_forecast"].combine_first(merged["Forecast"])
    merged["Final"] = merged["Final"].fillna(0).clip(lower=0)

    sum_bg = merged.groupby("ds")["Final"].sum().rename("SumBarangay").reset_index()
    chk = sum_bg.merge(city, on="ds", how="inner")

    if len(chk) != len(city):
        raise ValueError("Mismatch: city forecast dates do not align with barangay records.")

    chk["scale"] = chk["CityForecast"] / chk["SumBarangay"].replace(0, np.nan)
    chk["scale"] = chk["scale"].replace([np.inf, -np.inf], np.nan).fillna(1.0)
    scale_map = chk.set_index("ds")["scale"]

    merged["Final"] = merged["Final"] * merged["ds"].map(scale_map)
    merged["Final"] = merged["Final"].clip(lower=0)

    rec_sum = merged.groupby("ds")["Final"].sum().reset_index().merge(city, on="ds", how="left")
    diff = float((rec_sum["Final"] - rec_sum["CityForecast"]).abs().mean())
    print(f"✅ Reconciliation complete. Avg weekly diff vs city = {diff:.12f}")
    if diff > 1e-6:
        print("⚠️ Warning: Reconciliation mismatch exceeds tolerance.")

    merged = merged[
        ["Barangay_standardized", "ds", "Final", "Forecast", "local_forecast"]
    ].sort_values(["Barangay_standardized", "ds"])

    merged.to_csv(cfg.out / "barangay_forecasts_final.csv", index=False)
    print("✅ barangay_forecasts_final.csv written.")
    return merged
