# file: denguard/modeling/arima_model.py
from __future__ import annotations

from typing import Tuple, Dict, Any, Optional
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save


def smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    """
    Symmetric MAPE. Stable when values are near/at zero.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true) + np.abs(y_pred) + eps
    return float(np.mean(2.0 * np.abs(y_pred - y_true) / denom))


def fit_arima(
    train_city: pd.DataFrame,
    test_city: pd.DataFrame,
    cfg: Config,
    horizon: int,
) -> Tuple[bool, Any, Optional[pd.DataFrame], Dict[str, float]]:
    """
    Fit a NON-SEASONAL ARIMA (true ARIMA) using pmdarima.auto_arima
    on weekly city-level dengue counts.

    Returns:
        success: True if ARIMA ran successfully, False if ARIMA unavailable.
        model:   Fitted pmdarima model or None on failure.
        pred_df: DataFrame indexed by ds with yhat, yhat_lower, yhat_upper (test-aligned).
        metrics: Dict with RMSE, MAE, sMAPE (np.nan if ARIMA unavailable).
    """
    print("\n== STEP 8: ARIMA model ==")

    # ---- Input checks ----
    for name, df in (("train_city", train_city), ("test_city", test_city)):
        if not {"ds", "y"}.issubset(df.columns):
            raise ValueError(f"{name} must contain columns ['ds', 'y'].")

    # Work on copies to avoid mutating upstream dfs
    train_city = train_city.copy()
    test_city = test_city.copy()

    train_city["ds"] = pd.to_datetime(train_city["ds"], errors="raise")
    test_city["ds"] = pd.to_datetime(test_city["ds"], errors="raise")

    # Weekly series with explicit W-MON frequency
    y_train = train_city.set_index("ds")["y"].sort_index()
    y_train.index = pd.DatetimeIndex(y_train.index)
    y_train = y_train.asfreq("W-MON")

    y_test = test_city.set_index("ds")["y"].sort_index()
    y_test.index = pd.DatetimeIndex(y_test.index)
    y_test = y_test.asfreq("W-MON")

    # If this triggers, you have missing weeks in your city series
    if y_train.isna().any() or y_test.isna().any():
        raise ValueError(
            "NaNs detected after converting to weekly frequency. "
            "Ensure city_weekly has a row for every W-MON week (fill missing with 0 upstream)."
        )

    # ---- Import ARIMA dependency ----
    try:
        import pmdarima as pm
    except Exception as e:
        print("⚠️ ARIMA unavailable:", e)
        return False, None, None, {"RMSE": np.nan, "MAE": np.nan, "sMAPE": np.nan}

    from sklearn.metrics import mean_squared_error, mean_absolute_error

    # ---- Fit true ARIMA (non-seasonal) ----
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*force_all_finite.*", category=FutureWarning)

        model = pm.auto_arima(
            y_train,
            seasonal=False,   # TRUE ARIMA (not SARIMA)
            m=1,
            test="kpss",
            start_p=0, start_q=0,
            max_p=5, max_q=5,
            stepwise=True,
            trace=False,
            error_action="raise",
            suppress_warnings=False,
        )

    print(model.summary())

    # ---- Forecast + intervals (test evaluation alignment) ----
    future_h = int(horizon)
    if future_h <= 0:
        raise ValueError("Forecast horizon must be positive.")

    preds, conf = model.predict(
        n_periods=future_h,
        return_conf_int=True,
        alpha=0.2,  # 80% interval (matches Prophet interval_width=0.8)
    )

    preds = np.asarray(preds, dtype=float)
    conf = np.asarray(conf, dtype=float)

    # Evaluate only where test exists (if horizon > test length, we evaluate on test length)
    eval_len = min(len(y_test), future_h)
    if eval_len == 0:
        raise ValueError("No overlap between forecast horizon and test set.")

    eval_index = y_test.index[:eval_len]

    pred_df = pd.DataFrame(
        {
            "yhat": preds[:eval_len],
            "yhat_lower": conf[:eval_len, 0],
            "yhat_upper": conf[:eval_len, 1],
        },
        index=eval_index,
    )
    pred_df.index.name = "ds"

    if pred_df["yhat"].isna().any():
        raise ValueError("ARIMA produced NaN predictions on the evaluation horizon.")

    # ---- Metrics (RMSE, MAE, sMAPE) ----
    y_eval = y_test.iloc[:eval_len].to_numpy(dtype=float)
    yhat = pred_df["yhat"].to_numpy(dtype=float)

    metrics: Dict[str, float] = {
        "RMSE": float(np.sqrt(mean_squared_error(y_eval, yhat))),
        "MAE": float(mean_absolute_error(y_eval, yhat)),
        "sMAPE": smape(y_eval, yhat),
    }
    print("=== ARIMA Metrics ===", metrics)

    # ---- Residual diagnostics ----
    try:
        resid = np.asarray(model.resid(), dtype=float)
        # Residuals may be shorter than y_train; align to the tail
        resid_index = y_train.index[-len(resid):]
        resid_series = pd.Series(resid, index=resid_index)

        plt.figure(figsize=(9, 3))
        plt.plot(resid_series.index, resid_series.values)
        plt.title("ARIMA Residuals")
        plot_and_save(cfg.out / "arima_residuals.png")
    except Exception as e:
        print("ℹ️ Skipped ARIMA residual plot:", e)

    return True, model, pred_df, metrics
