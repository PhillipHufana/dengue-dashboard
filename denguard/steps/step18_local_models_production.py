from __future__ import annotations

from typing import List
import pandas as pd
import numpy as np
from denguard.config import Config
from denguard.steps.step18_local_models import _pad_local_grid
from denguard.forecast_schema import ensure_barangay_forecast_df

def local_models_production(
    barangay_keys: List[str],
    eligible_keys: List[str],
    weekly_full: pd.DataFrame,
    train_end: pd.Timestamp,
    horizon: int,
    PROPHET_OK: bool,
    cfg: Config,
) -> pd.DataFrame:
    """
    Production: fit local models using data up to train_end and output FUTURE forecasts only.
    No test metrics, no disagg comparison.
    Returns a long df with model_name in {local_prophet, local_arima} and horizon_type=future.
    """
    # Build a fake test_ds (empty) so we can reuse pad logic safely
    test_ds = pd.DatetimeIndex([])

    # Future starts after train_end (latest observed)
    future_ds = pd.date_range(start=train_end + pd.Timedelta(weeks=1), periods=horizon, freq="W-MON")

    # We will re-use your existing training logic by calling a tiny subset:
    # easiest: import your local model fitter bits from step18 or replicate minimal fit loops.
    # For now: create empty existing_long and rely on pad to fill zeros if a model fails.
    # BUT we DO want real forecasts → you’ll wire the actual fitting loop (below) in your step18 file.

    # --- Minimal: call your existing local_models_tierA is NOT possible because it requires test_city + disagg_test_df.
    # So production must have its own loop (copy Prophet/ARIMA fitting sections from step18, minus test parts).
    import pmdarima as pm
    import warnings

    long_parts = []
    all_keys = sorted(set(barangay_keys))
    eligible_set = set(eligible_keys)

    for bgy in all_keys:
        if bgy not in eligible_set:
            continue

        df_full = (
            weekly_full.loc[weekly_full["Barangay_key"] == bgy, ["WeekStart", "Cases"]]
            .rename(columns={"WeekStart": "ds", "Cases": "y"})
            .copy()
        )
        df_full["ds"] = pd.to_datetime(df_full["ds"], errors="coerce")
        df_full["y"] = pd.to_numeric(df_full["y"], errors="coerce").fillna(0.0)
        df_full = df_full.dropna(subset=["ds"]).groupby("ds", as_index=False).agg({"y": "sum"}).sort_values("ds")

        df_train = df_full[df_full["ds"] <= train_end].reset_index(drop=True)
        df_train = df_train.set_index("ds").asfreq("W-MON").fillna({"y": 0.0}).reset_index()

        # Prophet (future only)
        if PROPHET_OK:
            try:
                from prophet import Prophet
                mp = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False, interval_width=0.8)
                mp.fit(df_train[["ds", "y"]])
                fut = mp.make_future_dataframe(periods=horizon, freq="W-MON")
                fp = mp.predict(fut).set_index("ds").sort_index()
                p_fut_df = fp.reindex(future_ds)
                p_fut = np.clip(p_fut_df["yhat"].to_numpy(float), 0, None)

                if {"yhat_lower", "yhat_upper"}.issubset(p_fut_df.columns):
                    ci = np.clip(p_fut_df[["yhat_lower", "yhat_upper"]].to_numpy(float), 0, None)
                    lo, hi = ci[:, 0], ci[:, 1]
                else:
                    lo, hi = p_fut, p_fut

                raw_fut = pd.DataFrame({"Barangay_key": bgy, "ds": future_ds, "yhat": p_fut, "yhat_lower": lo, "yhat_upper": hi})
                long_parts.append(ensure_barangay_forecast_df(raw_fut, model_name="local_prophet", horizon_type="future"))
            except Exception:
                pass

        # ARIMA (future only)
        try:
            y_train = df_train.set_index("ds")["y"].sort_index()
            y_train.index = pd.DatetimeIndex(y_train.index)
            y_train = y_train.asfreq("W-MON").fillna(0.0)

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*force_all_finite.*", category=FutureWarning)
                ma = pm.auto_arima(y_train, seasonal=True, m=52, stepwise=True, suppress_warnings=True, error_action="ignore")

            try:
                pred_fut, conf_fut = ma.predict(n_periods=horizon, return_conf_int=True, alpha=0.2)
                ci = np.asarray(conf_fut, dtype=float)
                lo = np.clip(ci[:, 0], 0, None)
                hi = np.clip(ci[:, 1], 0, None)
            except Exception:
                pred_fut = ma.predict(n_periods=horizon)
                lo = hi = np.asarray(pred_fut, dtype=float)

            a_fut = np.clip(np.asarray(pred_fut, dtype=float), 0, None)
            raw_fut = pd.DataFrame({"Barangay_key": bgy, "ds": future_ds, "yhat": a_fut, "yhat_lower": lo, "yhat_upper": hi})
            long_parts.append(ensure_barangay_forecast_df(raw_fut, model_name="local_arima", horizon_type="future"))
        except Exception:
            pass

    existing = pd.concat(long_parts, ignore_index=True) if long_parts else pd.DataFrame(
        columns=["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]
    )

    # pad missing barangay/model combos to zeros (UI-safe)
    padded = _pad_local_grid(
        barangay_keys=all_keys,
        test_ds=test_ds,
        future_ds=future_ds,
        existing_long=existing,
    )
    padded = padded[padded["horizon_type"] == "future"].copy()
    padded["run_id"] = cfg.run_id
    padded.to_csv(cfg.out / "barangay_local_forecasts_long.csv", index=False)

    return padded
