from __future__ import annotations
from typing import Optional

import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save


def build_comparison_frame(
    y_test: pd.Series,
    forecast_arima: pd.Series,
    forecast_prophet: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Build a unified DataFrame with actual, ARIMA, and optional Prophet
    forecasts aligned on the test dates.
    """

    # Ensure datetime index + sorted (why: consistent alignment and plotting)
    if not isinstance(y_test.index, pd.DatetimeIndex):
        y_test.index = pd.to_datetime(y_test.index, errors="raise")
    y_test = y_test.sort_index()

    if not isinstance(forecast_arima.index, pd.DatetimeIndex):
        forecast_arima.index = pd.to_datetime(forecast_arima.index, errors="raise")
    forecast_arima = forecast_arima.sort_index()

    df = pd.DataFrame(index=y_test.index)
    df.index.name = "ds"

    df["actual"] = y_test
    df["arima"] = forecast_arima.reindex(df.index)

    if forecast_prophet is not None:
        p = (
            forecast_prophet.set_index("ds")
            .sort_index()
            .reindex(df.index)[["yhat"]]
        )
        df["prophet"] = p["yhat"]

    return df


def comparison_plot(
    y_test: pd.Series,
    forecast_arima: pd.Series,
    forecast_prophet: Optional[pd.DataFrame],
    cfg: Config
) -> None:
    print("\n== STEP 9: Prophet vs ARIMA (test period) ==")

    # Build aligned comparison frame
    comp_df = build_comparison_frame(y_test, forecast_arima, forecast_prophet)

    # Save table with forecasts and errors for inspection/export
    comp_with_errors = comp_df.copy()
    comp_with_errors["err_arima"] = comp_with_errors["actual"] - comp_with_errors["arima"]
    if "prophet" in comp_with_errors.columns:
        comp_with_errors["err_prophet"] = (
            comp_with_errors["actual"] - comp_with_errors["prophet"]
        )
    comp_with_errors.to_csv(cfg.out / "model_comparison_table.csv", index=True)

    # ---------- Plot 1: levels (Actual vs ARIMA vs Prophet) ----------
    plt.figure(figsize=(12, 5))

    plt.plot(comp_df.index, comp_df["actual"], label="Actual")

    if comp_df["arima"].notna().any():
        plt.plot(comp_df.index, comp_df["arima"], label="ARIMA")

    if "prophet" in comp_df.columns and comp_df["prophet"].notna().any():
        plt.plot(comp_df.index, comp_df["prophet"], label="Prophet")

    cutoff = pd.to_datetime(cfg.train_end_date) + pd.offsets.Week(weekday=0)
    plt.axvline(cutoff, color="gray", linestyle="--")

    plt.legend()
    plt.title("Prophet vs ARIMA Forecast Comparison (Test)")
    plot_and_save(cfg.out / "model_comparison.png")
    print("✅ Saved model comparison plot")

    # ---------- Plot 2: error curves (Actual - Forecast) ----------
    err_arima = comp_with_errors["err_arima"].dropna()

    err_prophet = None
    if "err_prophet" in comp_with_errors.columns:
        err_prophet = comp_with_errors["err_prophet"].dropna()
        if err_prophet.empty:
            err_prophet = None

    plt.figure(figsize=(12, 5))
    plt.axhline(0, color="gray", linestyle="--", linewidth=1)

    if not err_arima.empty:
        plt.plot(err_arima.index, err_arima.values, label="ARIMA error (actual - pred)")

    if err_prophet is not None:
        plt.plot(
            err_prophet.index,
            err_prophet.values,
            label="Prophet error (actual - pred)",
        )

    plt.title("Forecast Error Over Time (Test Period)")
    plt.legend()
    plot_and_save(cfg.out / "model_error_curves.png")
    print("✅ Saved model error curves plot and comparison table")
