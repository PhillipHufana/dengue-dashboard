from __future__ import annotations
from typing import Tuple, Dict
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from denguard.config import Config
from denguard.utils import plot_and_save

def fit_arima(
    train_city: pd.DataFrame,
    test_city: pd.DataFrame,
    cfg: Config
):
    print("\n== STEP 8: ARIMA model ==")
    from sklearn.metrics import mean_squared_error, mean_absolute_error, mean_absolute_percentage_error
    import pmdarima as pm

    y_train = train_city.set_index("ds")["y"]
    y_train.index = pd.DatetimeIndex(y_train.index, freq="W-MON")

    y_test = test_city.set_index("ds")["y"]
    y_test.index = pd.DatetimeIndex(y_test.index, freq="W-MON")

    model = pm.auto_arima(
        y_train,
        seasonal=True,
        m=52,
        test="kpss",
        seasonal_test="ocsb",
        start_p=1, start_q=1, max_p=3, max_q=3,
        start_P=1, start_Q=1, max_P=2, max_Q=2,
        stepwise=True,
        trace=False,
        error_action="raise",
        suppress_warnings=False,
    ).fit(y_train)

    print(model.summary())

    n_test = len(y_test)
    pred_test = pd.Series(model.predict(n_periods=n_test), index=y_test.index, name="yhat")

    if pred_test.isna().any():
        raise ValueError("ARIMA produced NaN predictions on test.")

    metrics = {
        "RMSE": float(np.sqrt(mean_squared_error(y_test, pred_test))),
        "MAE":  float(mean_absolute_error(y_test, pred_test)),
        "MAPE": float(mean_absolute_percentage_error(y_test, pred_test)),
    }
    print("=== ARIMA Metrics ===", metrics)

    try:
        resid = pd.Series(model.resid(), index=y_train.index)
        plt.figure(figsize=(9, 3))
        plt.plot(resid.index, resid.values)
        plt.title("ARIMA Residuals")
        plot_and_save(cfg.out / "arima_residuals.png")
    except Exception as e:
        print("ℹ️ Skipped ARIMA residual plot:", e)

    return model, pred_test, metrics, y_train, y_test
