from __future__ import annotations
from typing import Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from denguard.config import Config
from denguard.utils import plot_and_save

def barangay_error_ranking(
    weekly_full: pd.DataFrame,
    barangay_forecasts: pd.DataFrame,
    test_city: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    print("\n== STEP 13: Barangay-level error ranking (TEST ONLY) ==")
    test_ds = pd.DatetimeIndex(test_city["ds"])
    bgy_test = barangay_forecasts[barangay_forecasts["ds"].isin(test_ds)].copy()

    if bgy_test.empty:
        raise ValueError("Barangay test forecasts are empty. Check Step 10 outputs and date alignment.")

    truth = (
        weekly_full[weekly_full["WeekStart"].isin(test_ds)]
        .rename(columns={"WeekStart": "ds"})
        [["Barangay_standardized", "ds", "Cases"]]
    )

    eval_df = truth.merge(
        bgy_test[["Barangay_standardized", "ds", "Forecast"]],
        on=["Barangay_standardized", "ds"],
        how="inner",
    )

    if eval_df.empty:
        raise ValueError("No overlap between actual test weeks and barangay test forecasts.")

    from sklearn.metrics import mean_squared_error, mean_absolute_error, mean_absolute_percentage_error

    rows = []
    for bgy, g in eval_df.groupby("Barangay_standardized"):
        y_true = g["Cases"].to_numpy(dtype=float)
        y_pred = g["Forecast"].to_numpy(dtype=float)
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        mae  = float(mean_absolute_error(y_true, y_pred))
        try:
            mape = float(mean_absolute_percentage_error(y_true, y_pred))
        except Exception:
            denom = np.where(y_true == 0, np.nan, y_true)
            mape = float(np.nanmean(np.abs((y_true - y_pred) / denom)))
        rows.append({"Barangay": bgy, "RMSE": rmse, "MAE": mae, "MAPE": mape})

    barangay_errors = pd.DataFrame(rows)
    if barangay_errors.empty:
        raise ValueError("Computed no barangay error rows. Check input alignment.")

    barangay_errors["RMSE_rank"] = barangay_errors["RMSE"].rank(ascending=False, method="min")
    barangay_errors["MAE_rank"]  = barangay_errors["MAE"].rank(ascending=False, method="min")
    barangay_errors["MAPE_rank"] = barangay_errors["MAPE"].rank(ascending=False, method="min")
    barangay_errors["CompositeScore"] = barangay_errors[["RMSE_rank", "MAE_rank", "MAPE_rank"]].mean(axis=1)

    top_problematic = barangay_errors.sort_values("CompositeScore", ascending=False).head(10)
    print("\n🚩 Top 10 barangays with highest TEST forecast errors:")
    try:
        from IPython.display import display
        display(top_problematic)
    except Exception:
        print(top_problematic.to_string(index=False))

    barangay_errors.to_csv(cfg.out / "barangay_error_ranking.csv", index=False, encoding="utf-8-sig")
    print(f"✅ Barangay TEST error ranking saved to {cfg.out / 'barangay_error_ranking.csv'}")

    plt.figure(figsize=(10, 5))
    plt.barh(top_problematic["Barangay"].iloc[::-1], top_problematic["RMSE"].iloc[::-1])
    plt.title("Top 10 Barangays by RMSE (TEST window)")
    plt.xlabel("RMSE")
    plot_and_save(cfg.out / "barangay_error_top10.png")

    return barangay_errors