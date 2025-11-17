from __future__ import annotations
from typing import Dict, Optional, Tuple
import numpy as np
import numpy as _np
import pandas as pd

from denguard.config import Config

def select_city_model(
    metrics_prophet: Dict[str, float],
    metrics_arima: Dict[str, float],
    forecast_prophet: Optional[pd.DataFrame],
    forecast_arima_test: pd.Series,
    city_prophet: pd.DataFrame,
    y_train: pd.Series,
    cfg: Config,
    horizon: int,
) -> Tuple[str, pd.DataFrame]:
    use_prophet = (
        not np.isnan(metrics_prophet.get("RMSE", np.nan))
        and metrics_prophet["RMSE"] <= metrics_arima["RMSE"]
    )

    last_obs_ds = city_prophet["ds"].max()
    future_dates = pd.date_range(last_obs_ds + pd.Timedelta(weeks=1), periods=horizon, freq="W-MON")

    if use_prophet and forecast_prophet is not None:
        p_future = forecast_prophet[forecast_prophet["ds"].isin(future_dates)]
        if len(p_future) != len(future_dates):
            print("ℹ️ Prophet forecast missing some future rows; using flat fallback for gaps.")
            last_yhat = float(
                forecast_prophet.loc[forecast_prophet["ds"] == last_obs_ds, "yhat"].iloc[0]
            )
            chosen = pd.DataFrame(
                {"ds": future_dates, "yhat": last_yhat, "yhat_lower": np.nan, "yhat_upper": np.nan}
            )
        else:
            chosen = p_future[["ds", "yhat", "yhat_lower", "yhat_upper"]].reset_index(drop=True)
        chosen_model = "Prophet"
    else:
        import pmdarima as pm
        m = pm.auto_arima(
            y_train, seasonal=True, m=52,
            test="kpss", seasonal_test="ocsb",
            stepwise=True, error_action="raise", suppress_warnings=False,
        ).fit(y_train)
        yhat = _np.asarray(m.predict(n_periods=horizon), dtype=float)
        resid_std = float(pd.Series(m.resid()).std(ddof=1))
        chosen = pd.DataFrame(
            {
                "ds": future_dates,
                "yhat": yhat,
                "yhat_lower": yhat - 1.96 * resid_std,
                "yhat_upper": yhat + 1.96 * resid_std,
            }
        )
        chosen_model = "ARIMA"

    print(f"✅ Selected City Model: {chosen_model}")
    return chosen_model, chosen
