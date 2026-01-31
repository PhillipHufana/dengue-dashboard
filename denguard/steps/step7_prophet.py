from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd
from denguard.config import Config
from denguard.utils import plot_and_save
from denguard.forecast_schema import ensure_city_forecast_df, prophet_split_test_future


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
    City Prophet:
    Returns standardized forecast_test and forecast_future:
      ds, yhat, yhat_lower, yhat_upper, model_name, horizon_type
    """
    print("\n== STEP 7: Prophet model ==")

    for df_name, df in [("train_city", train_city), ("test_city", test_city)]:
        if not {"ds", "y"}.issubset(df.columns):
            raise ValueError(f"{df_name} must contain columns ['ds', 'y'].")

    try:
        from prophet import Prophet
    except Exception as e:
        print("⚠️ Prophet unavailable:", e)
        nan_metrics = {"RMSE": np.nan, "MAE": np.nan, "sMAPE": np.nan}
        return False, None, None, None, nan_metrics

    from sklearn.metrics import mean_squared_error, mean_absolute_error

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.3,
        seasonality_mode="additive",
        interval_width=0.8,
    )
    model.fit(train_city)

    future_h = int(horizon)
    if future_h <= 0:
        raise ValueError("Forecast horizon must be positive.")

    # Prophet makes full history + future. We'll split test/future explicitly.
    full_future = model.make_future_dataframe(periods=future_h, freq="W-MON")
    full_forecast = model.predict(full_future)

    # Define test and future date indices (Mondays)
    test_ds = pd.DatetimeIndex(pd.to_datetime(test_city["ds"], errors="raise")).sort_values()

    last_obs = pd.to_datetime(pd.concat([train_city["ds"], test_city["ds"]]).max())
    future_ds = pd.date_range(last_obs + pd.Timedelta(weeks=1), periods=future_h, freq="W-MON")

    raw_test, raw_future = prophet_split_test_future(full_forecast, test_ds=test_ds, future_ds=future_ds)

    # Standardize shapes + enforce interval cols exist
    forecast_test = ensure_city_forecast_df(raw_test.rename(columns={"y": "y"}), model_name="prophet", horizon_type="test")
    forecast_future = ensure_city_forecast_df(raw_future.rename(columns={"y": "y"}), model_name="prophet", horizon_type="future")

    # Metrics on test (aligned)
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
        print("ℹ️ Skipped Prophet component plotting:", e)

    return True, model, forecast_test, forecast_future, metrics
