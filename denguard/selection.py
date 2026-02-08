# denguard/selection.py
from __future__ import annotations
from typing import Dict, Optional, Tuple, Any

import numpy as np
import pandas as pd

from denguard.config import Config
from denguard.forecast_schema import ensure_city_forecast_df


def _safe_metric(metrics: Dict[str, float], key: str) -> float:
    val = metrics.get(key, np.nan)
    try:
        val_f = float(val)
    except (TypeError, ValueError):
        return float("inf")
    if np.isnan(val_f):
        return float("inf")
    return val_f


def select_city_model(
    metrics_prophet: Dict[str, float],
    metrics_arima: Dict[str, float],
    forecast_prophet_test: Optional[pd.DataFrame],
    forecast_arima_test: Optional[pd.DataFrame],
    city_prophet: pd.DataFrame,
    y_train: pd.Series,
    model_prophet: Any,
    model_arima: Any,
    cfg: Config,
    *,
    test_len: int,
    horizon: int,
) -> Tuple[str, pd.DataFrame]:
    """
    Returns:
      chosen_model: 'prophet' or 'arima'
      chosen_future: standardized city FUTURE forecast:
        ds, yhat, yhat_lower, yhat_upper, model_name, horizon_type='future'

    Backtest: test_len > 0 -> select by metrics
    Production: test_len == 0 -> choose cfg.production_city_model (fallback)
    """

    # ---------------------------------------------------------
    # A) Decide winner
    # ---------------------------------------------------------
    if test_len <= 0:
        # Production: no ground-truth test period, cannot compare metrics honestly.
        use_prophet = (getattr(cfg, "production_city_model", "prophet") == "prophet")
    else:
        def _better_is_prophet(key: str) -> Optional[bool]:
            p = _safe_metric(metrics_prophet, key)
            a = _safe_metric(metrics_arima, key)
            if np.isinf(p) and np.isinf(a):
                return None
            if np.isclose(p, a, rtol=1e-12, atol=1e-12):
                return None
            return p < a

        votes_prophet = 0
        votes_arima = 0
        for k in ("RMSE", "MAE", "sMAPE"):
            winner = _better_is_prophet(k)
            if winner is True:
                votes_prophet += 1
            elif winner is False:
                votes_arima += 1

        rmse_prophet = _safe_metric(metrics_prophet, "RMSE")
        rmse_arima = _safe_metric(metrics_arima, "RMSE")

        if votes_prophet == 0 and votes_arima == 0:
            if np.isinf(rmse_prophet) and np.isinf(rmse_arima):
                raise RuntimeError("Both models have invalid metrics; cannot select city model.")
            use_prophet = rmse_prophet <= rmse_arima
        else:
            if votes_prophet > votes_arima:
                use_prophet = True
            elif votes_arima > votes_prophet:
                use_prophet = False
            else:
                use_prophet = rmse_prophet <= rmse_arima

    # ---------------------------------------------------------
    # B) Build future dates from LAST OBSERVED WEEK
    # ---------------------------------------------------------
    last_obs_ds = pd.to_datetime(city_prophet["ds"], errors="raise").max()
    future_dates = pd.date_range(last_obs_ds + pd.Timedelta(weeks=1), periods=int(horizon), freq="W-MON")

    # ---------------------------------------------------------
    # C) Build future forecasts for each model
    # ---------------------------------------------------------
    def build_arima_future() -> Tuple[str, pd.DataFrame]:
        if model_arima is None:
            raise RuntimeError("ARIMA model is None.")
        # In backtest we want to generate beyond the test window; in production test_len=0 so this is just horizon.
        total_periods = int(test_len) + int(horizon)
        preds_full, conf = model_arima.predict(n_periods=total_periods, return_conf_int=True, alpha=0.2)
        preds_full = np.asarray(preds_full, dtype=float)
        conf = np.asarray(conf, dtype=float)

        preds_future = preds_full[int(test_len):]
        conf_future = conf[int(test_len):]

        raw = pd.DataFrame(
            {"ds": future_dates, "yhat": preds_future, "yhat_lower": conf_future[:, 0], "yhat_upper": conf_future[:, 1]}
        )
        return "arima", ensure_city_forecast_df(raw, model_name="arima", horizon_type="future")

    def build_prophet_future() -> Tuple[str, pd.DataFrame]:
        if model_prophet is None:
            raise RuntimeError("Prophet model is None.")
        total_periods = int(test_len) + int(horizon)
        future_full = model_prophet.make_future_dataframe(periods=total_periods, freq="W-MON")
        forecast_full = model_prophet.predict(future_full)
        fut = forecast_full[forecast_full["ds"] > last_obs_ds].copy().sort_values("ds").iloc[: int(horizon)]
        raw = fut[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        return "prophet", ensure_city_forecast_df(raw, model_name="prophet", horizon_type="future")

    # ---------------------------------------------------------
    # D) Choose + fallback
    # ---------------------------------------------------------
    if use_prophet:
        try:
            chosen_model, chosen_future = build_prophet_future()
        except Exception as e:
            print(f"ℹ️ Prophet chosen but failed for future: {e}. Falling back to ARIMA.")
            chosen_model, chosen_future = build_arima_future()
    else:
        chosen_model, chosen_future = build_arima_future()

    return chosen_model, chosen_future
