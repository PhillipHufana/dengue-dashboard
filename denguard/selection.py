# file: denguard/selection.py
from __future__ import annotations
from typing import Dict, Optional, Tuple, Any

import numpy as np
import pandas as pd

from denguard.config import Config


def _safe_metric(metrics: Dict[str, float], key: str) -> float:
    """
    Return metric value or +inf if missing/NaN.
    (why: treat invalid metrics as 'very bad' so the other model wins)
    """
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
    forecast_prophet: Optional[pd.DataFrame],  # used for plots / diagnostics elsewhere
    forecast_arima_test: pd.Series,            # not used here but kept for API compatibility
    city_prophet: pd.DataFrame,
    y_train: pd.Series,                        # not used here but harmless
    model_prophet: Any,
    model_arima: Any,
    cfg: Config,
    horizon: int,
) -> Tuple[str, pd.DataFrame]:
    """
    Select the best city model between Prophet and ARIMA using RMSE on TEST,
    then build a REAL future-horizon forecast DataFrame for the chosen model.

    Returns:
        chosen_model: "Prophet" or "ARIMA"
        chosen:       DataFrame with ['ds', 'yhat', 'yhat_lower', 'yhat_upper']
                      for the FUTURE horizon only (no historical or test rows).
    """

    # --- 0) RMSE comparison (NaN-safe) ---
    rmse_prophet = _safe_metric(metrics_prophet, "RMSE")
    rmse_arima = _safe_metric(metrics_arima, "RMSE")

    if np.isinf(rmse_prophet) and np.isinf(rmse_arima):
        raise RuntimeError("Both Prophet and ARIMA RMSE are invalid; cannot select city model.")

    use_prophet = rmse_prophet <= rmse_arima

    # --- 1) Common time info ---
    train_end = pd.to_datetime(cfg.train_end_date)
    # city_prophet contains full city history (train + test)
    mask_test = city_prophet["ds"] > train_end
    test_len = int(mask_test.sum())

    if test_len <= 0:
        raise RuntimeError(
            f"No test period found after train_end_date={cfg.train_end_date}; "
            "cannot split test vs future."
        )

    # Last observed week in the actual data = end of test period
    last_obs_ds = city_prophet["ds"].max()

    # Future weeks (for *deployment*) are horizon weeks AFTER the last observed ds
    future_dates = pd.date_range(
        last_obs_ds + pd.Timedelta(weeks=1),
        periods=horizon,
        freq="W-MON",
    )

    # --- Helper: ARIMA future (train_end -> test -> future) ---
    def build_arima_future() -> Tuple[str, pd.DataFrame]:
        if model_arima is None:
            raise RuntimeError("ARIMA model is None; cannot generate future forecast.")

        # Predict from immediately after train_end for test_len + horizon weeks
        total_periods = test_len + horizon
        preds_full = np.asarray(model_arima.predict(n_periods=total_periods), dtype=float)

        if len(preds_full) != total_periods:
            raise RuntimeError(
                f"ARIMA returned {len(preds_full)} predictions but expected {total_periods} "
                f"(test_len={test_len}, horizon={horizon})."
            )

        # First test_len steps = test predictions, last horizon steps = real future
        preds_future = preds_full[test_len:]

        # Simple ±1.96 * residual std for intervals
        resid = getattr(model_arima, "resid", None)
        if resid is None:
            resid_std = float("nan")
        else:
            resid_series = pd.Series(resid())
            resid_std = float(resid_series.std(ddof=1))

        if np.isnan(resid_std):
            yhat_lower = np.full_like(preds_future, np.nan, dtype=float)
            yhat_upper = np.full_like(preds_future, np.nan, dtype=float)
        else:
            yhat_lower = preds_future - 1.96 * resid_std
            yhat_upper = preds_future + 1.96 * resid_std

        chosen = pd.DataFrame(
            {
                "ds": future_dates,
                "yhat": preds_future,
                "yhat_lower": yhat_lower,
                "yhat_upper": yhat_upper,
            }
        )
        return "ARIMA", chosen

    # --- Helper: Prophet future (train_end -> test -> future) ---
    def build_prophet_future() -> Tuple[str, pd.DataFrame]:
        if model_prophet is None:
            raise RuntimeError("Prophet model is None; cannot generate future forecast.")

        # Ask Prophet for test_len + horizon weeks *beyond train_end*
        total_periods = test_len + horizon
        future_full = model_prophet.make_future_dataframe(
            periods=total_periods,
            freq="W-MON",
        )
        forecast_full = model_prophet.predict(future_full)

        # We only want the FUTURE beyond the last observed city week
        fut = forecast_full[forecast_full["ds"] > last_obs_ds].copy().sort_values("ds")

        if len(fut) < horizon:
            raise RuntimeError(
                f"Prophet produced only {len(fut)} future points beyond last_obs_ds={last_obs_ds}, "
                f"but horizon={horizon}. Check date alignment & freq."
            )

        p_future = fut.iloc[:horizon]

        chosen = (
            p_future[["ds", "yhat", "yhat_lower", "yhat_upper"]]
            .reset_index(drop=True)
        )
        return "Prophet", chosen

    # --- 2) Choose which model to use for the FUTURE ---
    if use_prophet and not np.isinf(rmse_prophet):
        try:
            chosen_model, chosen = build_prophet_future()
        except Exception as e:
            # Fallback to ARIMA if Prophet fails to produce a usable future
            print(
                f"ℹ️ Prophet selected by RMSE but failed to build future horizon: {e}. "
                "Falling back to ARIMA for city-level future forecast."
            )
            chosen_model, chosen = build_arima_future()
    else:
        chosen_model, chosen = build_arima_future()

    print(
        f"✅ Selected City Model (for future): {chosen_model} "
        f"(Prophet RMSE={rmse_prophet:.4f}, ARIMA RMSE={rmse_arima:.4f})"
    )
    return chosen_model, chosen
