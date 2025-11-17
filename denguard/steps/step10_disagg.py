from __future__ import annotations
from typing import Tuple, Optional
import numpy as np
import pandas as pd

from denguard.config import Config

def hybrid_disaggregation(
    chosen_city_model: str,
    chosen_city_future: pd.DataFrame,
    forecast_prophet: Optional[pd.DataFrame],
    forecast_arima_test: pd.Series,
    test_city: pd.DataFrame,
    weekly_full: pd.DataFrame,
    cfg: Config,
) -> Tuple[pd.DataFrame, float, pd.DataFrame]:
    print("\n== STEP 10: Hybrid top-down disaggregation (test + future, train-window weights) ==")

    if chosen_city_model == "Prophet" and forecast_prophet is not None:
        city_test = (
            test_city[["ds"]]
            .merge(forecast_prophet[["ds", "yhat"]], on="ds", how="left")
            .rename(columns={"yhat": "CityForecast"})
        )
    else:
        city_test = pd.DataFrame(
            {"ds": forecast_arima_test.index, "CityForecast": np.asarray(forecast_arima_test.values, dtype=float)}
        )

    city_test["CityLower"] = np.nan
    city_test["CityUpper"] = np.nan

    city_future = chosen_city_future.rename(
        columns={"yhat": "CityForecast", "yhat_lower": "CityLower", "yhat_upper": "CityUpper"}
    ).copy()

    combined_city = pd.concat([city_test, city_future], ignore_index=True).sort_values("ds")

    train_end = pd.to_datetime(cfg.train_end_date)
    recent_start = pd.to_datetime(cfg.recent_weight_start)
    recent = weekly_full[
        (weekly_full["WeekStart"] >= recent_start) &
        (weekly_full["WeekStart"] <= train_end)
    ].copy()

    if recent.empty:
        print("⚠️ Recent window empty. Falling back to full training history up to train_end.")
        recent = weekly_full[weekly_full["WeekStart"] <= train_end].copy()

    weights = (
        recent.groupby("Barangay_standardized")["Cases"]
        .sum()
        .reset_index(name="Cases")
    )
    total_recent = float(weights["Cases"].sum())
    if total_recent <= 0:
        raise ValueError("All-zero training-window cases; cannot compute weights.")
    weights["Proportion"] = weights["Cases"] / total_recent
    weights = weights[["Barangay_standardized", "Proportion"]]

    parts = []
    for _, row in weights.iterrows():
        b = row["Barangay_standardized"]
        p = float(row["Proportion"])
        tmp = combined_city.copy()
        tmp["Barangay_standardized"] = b
        tmp["Forecast"]       = tmp["CityForecast"] * p
        tmp["Forecast_lower"] = tmp["CityLower"] * p
        tmp["Forecast_upper"] = tmp["CityUpper"] * p
        parts.append(tmp)

    barangay_forecasts = pd.concat(parts, ignore_index=True)

    check = (
        barangay_forecasts.groupby("ds")["Forecast"].sum().reset_index()
        .merge(combined_city[["ds", "CityForecast"]], on="ds", how="left")
    )
    if (check["CityForecast"] == 0).any():
        raise ValueError("Zero city forecast encountered; cannot validate disaggregation.")
    diff = float((check["Forecast"] - check["CityForecast"]).abs().mean())
    print(f"✅ Validation — Avg weekly abs diff (sum barangays vs city): {diff:.6f}")

    barangay_forecasts.to_csv(cfg.out / "barangay_forecasts_hybrid.csv", index=False)
    check.to_csv(cfg.out / "city_vs_sum_check.csv", index=False)

    out_city = combined_city.copy()
    out_city["ModelUsed"] = chosen_city_model

    return barangay_forecasts, diff, out_city