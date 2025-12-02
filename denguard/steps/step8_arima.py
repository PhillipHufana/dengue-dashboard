# file: denguard/modeling/arima_model.py
from __future__ import annotations

from typing import Tuple, Dict, Any, Optional
import warnings  # <-- add this line
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save


def fit_arima(
    train_city: pd.DataFrame,
    test_city: pd.DataFrame,
    cfg: Config
) -> Tuple[bool, Any, Optional[pd.Series], Dict[str, float]]:
    """
    Train an ARIMA model using auto_arima on weekly dengue data
    and evaluate forecasts on the test period.

    Returns:
        success: True if ARIMA ran successfully, False if ARIMA is unavailable.
        model:   Fitted pmdarima model or None on failure.
        pred_test: Predictions aligned to the test period (subset if horizon < len(test)).
        metrics: Dict with RMSE, MAE, MAPE (np.nan if ARIMA unavailable).
    """

    print("\n== STEP 8: ARIMA model ==")

    # Schema validation (why: prevent cryptic ARIMA errors from bad input)
    for name, df in (("train_city", train_city), ("test_city", test_city)):
        if not {"ds", "y"}.issubset(df.columns):
            raise ValueError(f"{name} must contain columns ['ds', 'y'].")

    # Ensure datetime index (why: .asfreq + seasonal ARIMA expect regular DateTimeIndex)
    for df in (train_city, test_city):
        if not np.issubdtype(df["ds"].dtype, np.datetime64):
            df["ds"] = pd.to_datetime(df["ds"], errors="raise")

    # Convert to weekly series with explicit frequency
    y_train = (
        train_city.set_index("ds")["y"]
        .sort_index()
    )
    y_train.index = pd.DatetimeIndex(y_train.index)
    y_train = y_train.asfreq("W-MON")

    y_test = (
        test_city.set_index("ds")["y"]
        .sort_index()
    )
    y_test.index = pd.DatetimeIndex(y_test.index)
    y_test = y_test.asfreq("W-MON")

    # Guard against missing values after resampling (why: ARIMA will choke on NaNs)
    if y_train.isna().any() or y_test.isna().any():
        raise ValueError(
            "NaNs detected after converting to weekly frequency. "
            "Ensure there are no missing weeks or handle imputation upstream."
        )

    # Import dependencies (why: keep ARIMA optional)
    try:
        import pmdarima as pm
    except Exception as e:
        print("⚠️ ARIMA unavailable:", e)
        return False, None, None, {"RMSE": np.nan, "MAE": np.nan, "MAPE": np.nan}

    from sklearn.metrics import (
        mean_squared_error,
        mean_absolute_error,
        mean_absolute_percentage_error,
    )

    # Fit seasonal ARIMA (auto_arima returns fitted model)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            # message="'force_all_finite' was renamed to 'ensure_all_finite'",
            message=".*force_all_finite.*",  # regex, matches the full sklearn message
            category=FutureWarning,
        )

        model = pm.auto_arima(
            y_train,
            seasonal=True,
            m=52,                     # yearly seasonality for weekly data
            test="kpss",
            seasonal_test="ocsb",
            start_p=1, start_q=1,
            max_p=3,   max_q=3,
            start_P=1, start_Q=1,
            max_P=2,   max_Q=2,
            stepwise=True,
            trace=False,
            error_action="raise",
            suppress_warnings=False,
        )

    print(model.summary())

    # Forecast horizon (why: parity with Prophet, but avoid index-length mismatch)
    base_h = len(y_test)
    future_h = base_h if cfg.forecast_weeks_override is None else int(cfg.forecast_weeks_override)
    if future_h <= 0:
        raise ValueError("Forecast horizon must be positive.")

    # ARIMA forecasting
    preds = model.predict(n_periods=future_h)

    # Align predictions to available test horizon (why: allow override ≠ len(y_test))
    eval_len = min(len(y_test), future_h)
    if eval_len == 0:
        raise ValueError("No overlap between forecast horizon and test set.")

    eval_index = y_test.index[:eval_len]
    pred_test = pd.Series(preds[:eval_len], index=eval_index, name="yhat")

    if pred_test.isna().any():
        raise ValueError("ARIMA produced NaN predictions on the evaluation horizon.")

    # Metrics
    y_eval = y_test.iloc[:eval_len]
    metrics: Dict[str, float] = {
        "RMSE": float(np.sqrt(mean_squared_error(y_eval, pred_test))),
        "MAE": float(mean_absolute_error(y_eval, pred_test)),
        "MAPE": float(mean_absolute_percentage_error(y_eval, pred_test)),
    }
    print("=== ARIMA Metrics ===", metrics)

    # Residual plot (why: basic diagnostics for model fit)
    try:
        resid = pd.Series(model.resid(), index=y_train.index)
        plt.figure(figsize=(9, 3))
        plt.plot(resid.index, resid.values)
        plt.title("ARIMA Residuals")
        plot_and_save(cfg.out / "arima_residuals.png")
    except Exception as e:
        print("ℹ️ Skipped ARIMA residual plot:", e)

    return True, model, pred_test, metrics
