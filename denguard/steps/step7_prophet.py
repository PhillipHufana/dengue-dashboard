# file: denguard/modeling/prophet_model.py
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
) -> Tuple[bool, Any, Optional[pd.DataFrame], Dict[str, float]]:
    """
    Train a Prophet model on city-level dengue data and evaluate on test set.
    Ensures correct forecast horizon and Prophet-compatible formatting.
    """

    print("\n== STEP 7: Prophet model ==")

    # Validate required columns (why: avoid silent shape errors)
    for df_name, df in [("train_city", train_city), ("test_city", test_city)]:
        if not {"ds", "y"}.issubset(df.columns):
            raise ValueError(f"{df_name} must contain columns ['ds', 'y'].")

    # Prophet import guard (why: allow environments without Prophet)
    try:
        from prophet import Prophet
    except Exception as e:
        print("⚠️ Prophet unavailable:", e)
        return False, None, None, {"RMSE": np.nan, "MAE": np.nan, "MAPE": np.nan}

    from sklearn.metrics import (
        mean_squared_error,
        mean_absolute_error,
        mean_absolute_percentage_error,
    )

    # Model configuration (why: enforce consistent seasonal structure)
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.3,
        seasonality_mode="multiplicative",
        interval_width=0.8,
    )

    model.fit(train_city)

    # Forecast horizon (why: Prophet expects only future periods)
    future_h = (
        len(test_city)
        if cfg.forecast_weeks_override is None
        else int(cfg.forecast_weeks_override)
    )
    if future_h <= 0:
        raise ValueError("Forecast horizon must be positive.")

    # Generate future dates (why: avoid doubling test length)
    future = model.make_future_dataframe(periods=future_h, freq="W-MON")
    forecast = model.predict(future)

    # Evaluate only on matching test dates (why: Prophet returns full DF)
    joined = test_city.merge(forecast[["ds", "yhat"]], on="ds", how="left").dropna()
    if joined.empty:
        raise RuntimeError("Prophet produced no predictions for the test period.")

    metrics = {
        "RMSE": float(np.sqrt(mean_squared_error(joined["y"], joined["yhat"]))),
        "MAE":  float(mean_absolute_error(joined["y"], joined["yhat"])),
        "MAPE": float(mean_absolute_percentage_error(joined["y"], joined["yhat"])),
    }

    print("=== Prophet Metrics ===", metrics)

    # Optional plotting (why: Prophet occasionally fails on component plots)
    try:
        model.plot_components(forecast)
        plot_and_save(cfg.out / "prophet_components.png")
    except Exception as e:
        print("ℹ️ Skipped Prophet component plotting:", e)

    return True, model, forecast, metrics
