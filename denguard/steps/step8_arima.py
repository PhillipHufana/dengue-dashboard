# denguard/steps/step8_arima.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from denguard.config import Config
from denguard.forecast_schema import arima_pred_to_city_df, ensure_city_forecast_df
from denguard.utils import plot_and_save


def smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true) + np.abs(y_pred) + eps
    return float(np.mean(2.0 * np.abs(y_pred - y_true) / denom))


def _suppress_known_arima_warnings() -> None:
    warnings.filterwarnings("ignore", message=".*force_all_finite.*", category=FutureWarning)
    warnings.filterwarnings("ignore", message=".*ensure_all_finite.*", category=FutureWarning)
    warnings.filterwarnings(
        "ignore",
        message=".*Non-invertible starting MA parameters found.*",
        category=UserWarning,
    )


def fit_arima(
    train_city: pd.DataFrame,
    test_city: pd.DataFrame,
    cfg: Config,
    horizon: int,
) -> Tuple[bool, Any, Optional[pd.DataFrame], Dict[str, float]]:
    """
    Backtest (test_city non-empty):
      returns forecast_test + metrics
    Production (test_city empty):
      returns forecast_test=None + metrics=nan (model still returned, used later for future)

    ARIMA is required for the pipeline's compare-and-select methodology.
    Fail fast here if the dependency, fit, or forecast step is unavailable.
    """
    print("\n== STEP 8: ARIMA model ==")

    if not {"ds", "y"}.issubset(train_city.columns):
        raise ValueError("train_city must contain columns ['ds','y'].")

    if not test_city.empty and not {"ds", "y"}.issubset(test_city.columns):
        raise ValueError("test_city must contain columns ['ds','y'] when provided.")

    train_city = train_city.copy()
    train_city["ds"] = pd.to_datetime(train_city["ds"], errors="raise")
    train_city["y"] = pd.to_numeric(train_city["y"], errors="coerce").fillna(0.0)

    y_train = train_city.set_index("ds")["y"].sort_index().asfreq("W-MON")
    if y_train.isna().any():
        raise ValueError("NaNs after asfreq('W-MON') on y_train. Ensure weekly continuity upstream.")

    try:
        import pmdarima as pm
    except Exception as e:
        raise RuntimeError(f"ARIMA is required but pmdarima could not be imported: {e}") from e

    with warnings.catch_warnings():
        _suppress_known_arima_warnings()
        try:
            model = pm.auto_arima(
                y_train,
                seasonal=False,
                m=1,
                test="kpss",
                start_p=0,
                start_q=0,
                max_p=5,
                max_q=5,
                stepwise=True,
                trace=False,
                error_action="raise",
                suppress_warnings=False,
            )
        except Exception as e:
            raise RuntimeError(f"ARIMA fit failed during auto_arima(): {e}") from e

    print(model.summary())

    future_h = int(horizon)
    if future_h <= 0:
        raise ValueError("Forecast horizon must be positive.")

    with warnings.catch_warnings():
        _suppress_known_arima_warnings()
        try:
            preds, conf = model.predict(n_periods=future_h, return_conf_int=True, alpha=0.2)
            preds = np.asarray(preds, dtype=float)
            conf = np.asarray(conf, dtype=float)
        except Exception as e:
            raise RuntimeError(f"ARIMA forecast generation failed: {e}") from e

    if test_city.empty:
        try:
            resid = np.asarray(model.resid(), dtype=float)
            resid_index = y_train.index[-len(resid):]
            plt.figure(figsize=(9, 3))
            plt.plot(resid_index, resid)
            plt.title("ARIMA Residuals")
            plot_and_save(cfg.out / "arima_residuals.png")
        except Exception as e:
            print("Skipped ARIMA residual plot:", e)

        nan_metrics = {"RMSE": np.nan, "MAE": np.nan, "sMAPE": np.nan}
        return True, model, None, nan_metrics

    test_city = test_city.copy()
    test_city["ds"] = pd.to_datetime(test_city["ds"], errors="raise")
    test_city["y"] = pd.to_numeric(test_city["y"], errors="coerce").fillna(0.0)

    y_test = test_city.set_index("ds")["y"].sort_index().asfreq("W-MON")
    if y_test.isna().any():
        raise ValueError("NaNs after asfreq('W-MON') on y_test. Ensure weekly continuity upstream.")

    eval_len = min(len(y_test), future_h)
    eval_index = y_test.index[:eval_len]

    pred_df = pd.DataFrame(
        {"yhat": preds[:eval_len], "yhat_lower": conf[:eval_len, 0], "yhat_upper": conf[:eval_len, 1]},
        index=eval_index,
    )
    pred_df.index.name = "ds"

    y_eval = y_test.iloc[:eval_len].to_numpy(dtype=float)
    yhat = pred_df["yhat"].to_numpy(dtype=float)

    from sklearn.metrics import mean_absolute_error, mean_squared_error

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
        print("Skipped ARIMA residual plot:", e)

    raw_city_test = arima_pred_to_city_df(pred_df)
    forecast_test = ensure_city_forecast_df(raw_city_test, model_name="arima", horizon_type="test")

    return True, model, forecast_test, metrics
