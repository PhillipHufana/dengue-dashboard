from __future__ import annotations
from typing import Optional
import pandas as pd
import matplotlib.pyplot as plt
from denguard.config import Config
from denguard.utils import plot_and_save

def comparison_plot(
    y_test: pd.Series,
    forecast_arima: pd.Series,
    forecast_prophet: Optional[pd.DataFrame],
    cfg: Config
) -> None:
    print("\n== STEP 9: Prophet vs ARIMA (test period) ==")
    plt.figure(figsize=(12, 5))
    plt.plot(y_test.index, y_test.values, label="Actual")
    plt.plot(forecast_arima.index, forecast_arima.values, label="ARIMA")

    if forecast_prophet is not None:
        p_test = (
            forecast_prophet.set_index("ds")
            .reindex(y_test.index)[["yhat"]]
            .dropna()
        )
        if not p_test.empty:
            plt.plot(p_test.index, p_test["yhat"].values, label="Prophet")

    cutoff = pd.to_datetime(cfg.train_end_date) + pd.offsets.Week(weekday=0)
    plt.axvline(cutoff, color="gray", linestyle="--")
    plt.legend()
    plt.title("Prophet vs ARIMA Forecast Comparison (Test)")
    plot_and_save(cfg.out / "model_comparison.png")
    print("✅ Saved model comparison plot")
