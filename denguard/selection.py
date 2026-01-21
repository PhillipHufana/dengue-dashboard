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
    Select the best city model between Prophet and ARIMA using joint TEST metrics
    (RMSE, MAE, sMAPE) via majority vote

    Returns:
        chosen_model: "Prophet" or "ARIMA"
        chosen:       DataFrame with ['ds', 'yhat', 'yhat_lower', 'yhat_upper']
                      for the FUTURE horizon only (no historical or test rows).
    """

        # --- 0) Joint metric selection: RMSE + MAE + sMAPE (NaN-safe) ---

    def _better_is_prophet(key: str) -> Optional[bool]:
        """
        Returns:
            True  -> Prophet strictly better on this metric
            False -> ARIMA strictly better on this metric
            None  -> cannot compare (both invalid or equal)
        """
        p = _safe_metric(metrics_prophet, key)
        a = _safe_metric(metrics_arima, key)

        # If both invalid, no vote
        if np.isinf(p) and np.isinf(a):
            return None

        # If exactly equal (or extremely close), no vote
        if np.isclose(p, a, rtol=1e-12, atol=1e-12):
            return None

        return p < a  # lower is better

    votes_prophet = 0
    votes_arima = 0
    for k in ("RMSE", "MAE", "sMAPE"):
        winner = _better_is_prophet(k)
        if winner is True:
            votes_prophet += 1
        elif winner is False:
            votes_arima += 1

    # Tie-breaker uses RMSE (still NaN-safe)
    rmse_prophet = _safe_metric(metrics_prophet, "RMSE")
    rmse_arima = _safe_metric(metrics_arima, "RMSE")

    if votes_prophet == 0 and votes_arima == 0:
        # nothing comparable; fall back to RMSE if possible
        if np.isinf(rmse_prophet) and np.isinf(rmse_arima):
            raise RuntimeError("Both models have invalid metrics; cannot select city model.")
        use_prophet = rmse_prophet <= rmse_arima
        decision_rule = "fallback_to_RMSE"
    else:
        if votes_prophet > votes_arima:
            use_prophet = True
            decision_rule = "majority_vote"
        elif votes_arima > votes_prophet:
            use_prophet = False
            decision_rule = "majority_vote"
        else:
            # 1–1–0 tie or 1–1–1 tie (if you ever add metrics): break by RMSE
            use_prophet = rmse_prophet <= rmse_arima
            decision_rule = "tie_break_by_RMSE"

    print(
        "=== City model selection (test) === "
        f"votes Prophet={votes_prophet}, ARIMA={votes_arima}, rule={decision_rule} | "
        f"RMSE P={rmse_prophet:.4f} A={rmse_arima:.4f} | "
        f"MAE P={_safe_metric(metrics_prophet,'MAE'):.4f} A={_safe_metric(metrics_arima,'MAE'):.4f} | "
        f"sMAPE P={_safe_metric(metrics_prophet,'sMAPE'):.4f} A={_safe_metric(metrics_arima,'sMAPE'):.4f}"
    )


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
        preds_full, conf = model_arima.predict(
            n_periods=total_periods,
            return_conf_int=True,
            alpha=0.2,
        )
        preds_full = np.asarray(preds_full, dtype=float)
        conf = np.asarray(conf, dtype=float)

        preds_future = preds_full[test_len:]
        conf_future = conf[test_len:]

        chosen = pd.DataFrame(
            {
                "ds": future_dates,
                "yhat": preds_future,
                "yhat_lower": conf_future[:, 0],
                "yhat_upper": conf_future[:, 1],
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

    print(f"✅ Selected City Model (for future): {chosen_model}")

    return chosen_model, chosen
