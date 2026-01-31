from __future__ import annotations

from typing import Tuple, Dict, Any, Optional
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save
from denguard.forecast_schema import ensure_city_forecast_df, arima_pred_to_city_df


def smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
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
    City ARIMA:
    Returns standardized forecast_test:
      ds, yhat, yhat_lower, yhat_upper, model_name, horizon_type
    """
    print("\n== STEP 8: ARIMA model ==")

    for name, df in (("train_city", train_city), ("test_city", test_city)):
        if not {"ds", "y"}.issubset(df.columns):
            raise ValueError(f"{name} must contain columns ['ds', 'y'].")

    train_city = train_city.copy()
    test_city = test_city.copy()
    train_city["ds"] = pd.to_datetime(train_city["ds"], errors="raise")
    test_city["ds"] = pd.to_datetime(test_city["ds"], errors="raise")

    y_train = train_city.set_index("ds")["y"].sort_index().asfreq("W-MON")
    y_test = test_city.set_index("ds")["y"].sort_index().asfreq("W-MON")

    if y_train.isna().any() or y_test.isna().any():
        raise ValueError("NaNs after asfreq('W-MON'). Ensure city_weekly has all weeks (fill upstream).")

    try:
        import pmdarima as pm
    except Exception as e:
        print("⚠️ ARIMA unavailable:", e)
        return False, None, None, {"RMSE": np.nan, "MAE": np.nan, "sMAPE": np.nan}

    from sklearn.metrics import mean_squared_error, mean_absolute_error

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*force_all_finite.*", category=FutureWarning)
        model = pm.auto_arima(
            y_train,
            seasonal=False,
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

    future_h = int(horizon)
    if future_h <= 0:
        raise ValueError("Forecast horizon must be positive.")

    preds, conf = model.predict(n_periods=future_h, return_conf_int=True, alpha=0.2)
    preds = np.asarray(preds, dtype=float)
    conf = np.asarray(conf, dtype=float)

    eval_len = min(len(y_test), future_h)
    eval_index = y_test.index[:eval_len]

    pred_df = pd.DataFrame(
        {"yhat": preds[:eval_len], "yhat_lower": conf[:eval_len, 0], "yhat_upper": conf[:eval_len, 1]},
        index=eval_index,
    )
    pred_df.index.name = "ds"

    y_eval = y_test.iloc[:eval_len].to_numpy(dtype=float)
    yhat = pred_df["yhat"].to_numpy(dtype=float)

    metrics: Dict[str, float] = {
        "RMSE": float(np.sqrt(mean_squared_error(y_eval, yhat))),
        "MAE": float(mean_absolute_error(y_eval, yhat)),
        "sMAPE": smape(y_eval, yhat),
    }
    print("=== ARIMA Metrics ===", metrics)

    try:
        resid = np.asarray(model.resid(), dtype=float)
        resid_index = y_train.index[-len(resid):]
        plt.figure(figsize=(9, 3))
        plt.plot(resid_index, resid)
        plt.title("ARIMA Residuals")
        plot_and_save(cfg.out / "arima_residuals.png")
    except Exception as e:
        print("ℹ️ Skipped ARIMA residual plot:", e)

    # Standardize to city schema with ds column
    raw_city_test = arima_pred_to_city_df(pred_df)
    forecast_test = ensure_city_forecast_df(raw_city_test, model_name="arima", horizon_type="test")

    return True, model, forecast_test, metrics

