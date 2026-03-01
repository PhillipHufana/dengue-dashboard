# denguard/steps/step7_prophet.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from denguard.config import Config
from denguard.forecast_schema import ensure_city_forecast_df, prophet_split_test_future
from denguard.utils import plot_and_save


def smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true) + np.abs(y_pred) + eps
    return float(np.mean(2.0 * np.abs(y_pred - y_true) / denom))


def fit_prophet(
    train_city: pd.DataFrame,
    test_city: pd.DataFrame,
    cfg: Config,
    horizon: int,
) -> Tuple[bool, Any, Optional[pd.DataFrame], Optional[pd.DataFrame], Dict[str, float]]:
    """
    Backtest (test_city non-empty):
      returns forecast_test + forecast_future + metrics
    Production (test_city empty):
      returns forecast_test=None, forecast_future valid, metrics=nan

    Prophet is required for the pipeline's compare-and-select methodology.
    Fail fast here if the dependency, fit, or forecast step is unavailable.
    """
    print("\n== STEP 7: Prophet model ==")

    if not {"ds", "y"}.issubset(train_city.columns):
        raise ValueError("train_city must contain columns ['ds','y'].")

    if not test_city.empty and not {"ds", "y"}.issubset(test_city.columns):
        raise ValueError("test_city must contain columns ['ds','y'] when provided.")

    try:
        from prophet import Prophet
    except Exception as e:
        raise RuntimeError(f"Prophet is required but could not be imported: {e}") from e

    from sklearn.metrics import mean_absolute_error, mean_squared_error

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_mode="additive",
        interval_width=0.95,
    )
    try:
        model.fit(train_city[["ds", "y"]])
    except Exception as e:
        raise RuntimeError(f"Prophet fit failed: {e}") from e

    future_h = int(horizon)
    if future_h <= 0:
        raise ValueError("Forecast horizon must be positive.")

    if test_city.empty:
        last_obs = pd.to_datetime(train_city["ds"], errors="raise").max()
        try:
            future_full = model.make_future_dataframe(periods=future_h, freq="W-MON")
            forecast_full = model.predict(future_full)
        except Exception as e:
            raise RuntimeError(f"Prophet forecast generation failed: {e}") from e

        fut = forecast_full[forecast_full["ds"] > last_obs].copy().sort_values("ds").iloc[:future_h]
        raw_future = fut[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()

        forecast_future = ensure_city_forecast_df(raw_future, model_name="prophet", horizon_type="future")
        nan_metrics = {"RMSE": np.nan, "MAE": np.nan, "sMAPE": np.nan}
        return True, model, None, forecast_future, nan_metrics

    test_ds = pd.DatetimeIndex(pd.to_datetime(test_city["ds"], errors="raise")).sort_values()

    try:
        full_future = model.make_future_dataframe(periods=len(test_ds) + future_h, freq="W-MON")
        full_forecast = model.predict(full_future)
    except Exception as e:
        raise RuntimeError(f"Prophet forecast generation failed: {e}") from e

    last_obs = pd.to_datetime(pd.concat([train_city["ds"], test_city["ds"]]).max())
    future_ds = pd.date_range(last_obs + pd.Timedelta(weeks=1), periods=future_h, freq="W-MON")

    raw_test, raw_future = prophet_split_test_future(full_forecast, test_ds=test_ds, future_ds=future_ds)

    forecast_test = ensure_city_forecast_df(raw_test, model_name="prophet", horizon_type="test")
    forecast_future = ensure_city_forecast_df(raw_future, model_name="prophet", horizon_type="future")

    joined = test_city.merge(forecast_test[["ds", "yhat"]], on="ds", how="left").dropna()
    if joined.empty:
        raise RuntimeError("Prophet produced no predictions for the test period.")

    metrics = {
        "RMSE": float(np.sqrt(mean_squared_error(joined["y"], joined["yhat"]))),
        "MAE": float(mean_absolute_error(joined["y"], joined["yhat"])),
        "sMAPE": smape(joined["y"].to_numpy(), joined["yhat"].to_numpy()),
    }
    print("=== Prophet Metrics ===", metrics)

    try:
        model.plot_components(full_forecast)
        plot_and_save(cfg.out / "prophet_components.png")
    except Exception as e:
        print("â„¹ï¸ Skipped Prophet component plotting:", e)

    return True, model, forecast_test, forecast_future, metrics
