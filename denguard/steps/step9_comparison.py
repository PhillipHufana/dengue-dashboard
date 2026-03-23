from __future__ import annotations

from typing import Optional
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save


def comparison_plot(
    y_test: pd.Series,
    city_arima_test: pd.DataFrame,     # standardized: ds,yhat,...
    city_prophet_test: Optional[pd.DataFrame],  # standardized: ds,yhat,...
    cfg: Config,
) -> None:
    print("\n== STEP 9: Prophet vs ARIMA (test period) ==")

    if not isinstance(y_test.index, pd.DatetimeIndex):
        y_test.index = pd.to_datetime(y_test.index, errors="raise")
    y_test = y_test.sort_index()

    df = pd.DataFrame(index=y_test.index)
    df.index.name = "ds"
    df["actual"] = y_test

    ar = city_arima_test.copy()
    ar["ds"] = pd.to_datetime(ar["ds"], errors="raise")
    ar = ar.set_index("ds").sort_index()
    df["arima"] = ar["yhat"].reindex(df.index)

    if city_prophet_test is not None and not city_prophet_test.empty:
        pr = city_prophet_test.copy()
        pr["ds"] = pd.to_datetime(pr["ds"], errors="raise")
        pr = pr.set_index("ds").sort_index()
        df["prophet"] = pr["yhat"].reindex(df.index)

    comp_with_errors = df.copy()
    comp_with_errors["err_arima"] = comp_with_errors["actual"] - comp_with_errors["arima"]
    if "prophet" in comp_with_errors.columns:
        comp_with_errors["err_prophet"] = comp_with_errors["actual"] - comp_with_errors["prophet"]
    comp_with_errors.to_csv(cfg.out / "model_comparison_table.csv", index=True)
    print(" Saved:", cfg.out / "model_comparison_table.csv")

    plt.figure(figsize=(12, 5))
    plt.plot(df.index, df["actual"], label="Actual")
    if df["arima"].notna().any():
        plt.plot(df.index, df["arima"], label="ARIMA")
    if "prophet" in df.columns and df["prophet"].notna().any():
        plt.plot(df.index, df["prophet"], label="Prophet")
    plt.legend()
    plt.title("Prophet vs ARIMA Forecast Comparison (Test)")
    plot_and_save(cfg.out / "model_comparison.png")
    print(" Saved:", cfg.out / "model_comparison.png")

    plt.figure(figsize=(12, 5))
    plt.axhline(0, color="gray", linestyle="--", linewidth=1)
    ea = comp_with_errors["err_arima"].dropna()
    if not ea.empty:
        plt.plot(ea.index, ea.values, label="ARIMA error (actual - pred)")
    if "err_prophet" in comp_with_errors.columns:
        ep = comp_with_errors["err_prophet"].dropna()
        if not ep.empty:
            plt.plot(ep.index, ep.values, label="Prophet error (actual - pred)")
    plt.title("Forecast Error Over Time (Test Period)")
    plt.legend()
    plot_and_save(cfg.out / "model_error_curves.png")
    print(" Saved:", cfg.out / "model_error_curves.png")

