from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save, smape


def barangay_error_ranking(
    weekly_full: pd.DataFrame,
    barangay_forecasts_test: pd.DataFrame,
    test_city: pd.DataFrame,
    cfg: Config,
    model_name_for_eval: str = "disagg",
) -> pd.DataFrame:
    """
    TEST-only performance ranking.

    Expects barangay_forecasts_test standardized barangay df:
      Barangay_key, ds, yhat, ..., model_name, horizon_type='test'

    Notes:
      - Uses sMAPE + RMSE + MAE (sMAPE is stable with zeros).
      - Keeps MAPE only if you explicitly want it (not recommended for sparse series).
    """
    print("\n== STEP 13: Barangay-level error ranking (TEST ONLY, standardized) ==")

    test_ds = pd.DatetimeIndex(pd.to_datetime(test_city["ds"], errors="raise")).sort_values()

    bgy_test = barangay_forecasts_test.copy()
    bgy_test["ds"] = pd.to_datetime(bgy_test["ds"], errors="raise")

    # Use only test horizon + chosen model_name if present
    if "horizon_type" in bgy_test.columns:
        bgy_test = bgy_test[bgy_test["horizon_type"] == "test"].copy()
    if "model_name" in bgy_test.columns:
        bgy_test = bgy_test[bgy_test["model_name"] == model_name_for_eval].copy()

    bgy_test = bgy_test[bgy_test["ds"].isin(test_ds)].copy()
    if bgy_test.empty:
        raise ValueError("Barangay test forecasts empty. Check Step 10 outputs and date alignment.")

    truth = (
        weekly_full[weekly_full["WeekStart"].isin(test_ds)]
        .rename(columns={"WeekStart": "ds"})
        [["Barangay_key", "ds", "Cases"]]
        .copy()
    )
    truth["ds"] = pd.to_datetime(truth["ds"], errors="raise")

    eval_df = truth.merge(
        bgy_test[["Barangay_key", "ds", "yhat"]],
        on=["Barangay_key", "ds"],
        how="inner",
    )
    if eval_df.empty:
        raise ValueError("No overlap between actual test weeks and barangay test forecasts.")

    from sklearn.metrics import mean_squared_error, mean_absolute_error

    rows = []
    for bgy, g in eval_df.groupby("Barangay_key"):
        y_true = g["Cases"].to_numpy(dtype=float)
        y_pred = g["yhat"].to_numpy(dtype=float)

        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        mae = float(mean_absolute_error(y_true, y_pred))
        smape_v = float(smape(y_true, y_pred))

        rows.append({"Barangay_key": bgy, "RMSE": rmse, "MAE": mae, "sMAPE": smape_v})

    barangay_errors = pd.DataFrame(rows)
    if barangay_errors.empty:
        raise ValueError("Computed no barangay error rows. Check input alignment.")

    # Higher score = worse
    barangay_errors["RMSE_rank"] = barangay_errors["RMSE"].rank(ascending=False, method="min")
    barangay_errors["MAE_rank"] = barangay_errors["MAE"].rank(ascending=False, method="min")
    barangay_errors["sMAPE_rank"] = barangay_errors["sMAPE"].rank(ascending=False, method="min")
    barangay_errors["CompositeScore"] = barangay_errors[["RMSE_rank", "MAE_rank", "sMAPE_rank"]].mean(axis=1)

    top_problematic = barangay_errors.sort_values("CompositeScore", ascending=False).head(10)
    print("\n🚩 Top 10 barangays with highest TEST forecast errors:")
    print(top_problematic.to_string(index=False))

    barangay_errors.to_csv(cfg.out / "barangay_error_ranking.csv", index=False, encoding="utf-8-sig")
    print(f"✅ Barangay TEST error ranking saved to {cfg.out / 'barangay_error_ranking.csv'}")

    plt.figure(figsize=(10, 5))
    plt.barh(top_problematic["Barangay_key"].iloc[::-1], top_problematic["RMSE"].iloc[::-1])
    plt.title("Top 10 Barangays by RMSE (TEST window)")
    plt.xlabel("RMSE")
    plot_and_save(cfg.out / "barangay_error_top10.png")

    return barangay_errors
