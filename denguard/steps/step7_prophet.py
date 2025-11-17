from __future__ import annotations
from typing import Dict, Optional, Tuple, Any
import numpy as np
import pandas as pd
from denguard.config import Config
from denguard.utils import plot_and_save

def fit_prophet(
    train_city: pd.DataFrame,
    test_city: pd.DataFrame,
    cfg: Config
):
    print("\n== STEP 7: Prophet model ==")
    try:
        from prophet import Prophet
    except Exception as e:
        print("⚠️ Prophet unavailable:", e)
        return False, None, None, {"RMSE": np.nan, "MAE": np.nan, "MAPE": np.nan}

    from sklearn.metrics import mean_squared_error, mean_absolute_error, mean_absolute_percentage_error

    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.3,
        seasonality_mode="multiplicative",
        interval_width=0.8,
    )
    m.fit(train_city)

    future_h = len(test_city) if cfg.forecast_weeks_override is None else int(cfg.forecast_weeks_override)
    if future_h <= 0:
        raise ValueError("Future horizon must be positive.")

    n_append = len(test_city) + future_h
    future = m.make_future_dataframe(periods=n_append, freq="W-MON")
    fcst = m.predict(future)

    test_join = test_city.merge(fcst[["ds", "yhat"]], on="ds", how="left").dropna()
    if test_join.empty:
        raise RuntimeError("Prophet produced no predictions on the test dates.")
    metrics = {
        "RMSE": float(np.sqrt(mean_squared_error(test_join["y"], test_join["yhat"]))),
        "MAE":  float(mean_absolute_error(test_join["y"], test_join["yhat"])),
        "MAPE": float(mean_absolute_percentage_error(test_join["y"], test_join["yhat"])),
    }
    print("=== Prophet Metrics ===", metrics)

    try:
        m.plot_components(fcst)
        plot_and_save(cfg.out / "prophet_components.png")
    except Exception as e:
        print("ℹ️ Skipped Prophet component plotting:", e)

    return True, m, fcst, metrics