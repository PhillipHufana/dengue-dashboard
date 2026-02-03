# ============================================================
# file: denguard/steps/step18_local_models.py
# (PATCHED) pad missing local model rows with zeros for UI
# ============================================================
from __future__ import annotations

from typing import List, Tuple, Dict, Any
import numpy as np
import pandas as pd
import warnings

from denguard.config import Config
from denguard.forecast_schema import ensure_barangay_forecast_df


def _pad_local_grid(

    tierA: List[str],
    test_ds: pd.DatetimeIndex,
    future_ds: pd.DatetimeIndex,
    existing_long: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ensures every TierA barangay has rows for both local models for all ds
    in both test and future horizons. Missing rows are filled with yhat=0.
    """
    # Safety: ensure TierA keys are unique + stable ordering
    tierA = sorted(set(tierA))
    models = ["local_prophet", "local_arima"]

    def _template(ds: pd.DatetimeIndex, horizon_type: str) -> pd.DataFrame:
        mi = pd.MultiIndex.from_product([tierA, ds, models], names=["Barangay_key", "ds", "model_name"])
        tmp = mi.to_frame(index=False)
        tmp["yhat"] = 0.0
        tmp["yhat_lower"] = 0.0
        tmp["yhat_upper"] = 0.0
        tmp["horizon_type"] = horizon_type
        return tmp

    tmpl_test = _template(test_ds, "test")
    tmpl_fut = _template(future_ds, "future")
    tmpl = pd.concat([tmpl_test, tmpl_fut], ignore_index=True)

    ex = existing_long.copy()
    if ex.empty:
        merged = tmpl
    else:
        ex["ds"] = pd.to_datetime(ex["ds"], errors="raise")
        merged = tmpl.merge(
            ex[["Barangay_key", "ds", "model_name", "horizon_type", "yhat", "yhat_lower", "yhat_upper"]],
            on=["Barangay_key", "ds", "model_name", "horizon_type"],
            how="left",
            suffixes=("_t", ""),
        )
        for c in ["yhat", "yhat_lower", "yhat_upper"]:
            merged[c] = merged[c].fillna(merged[f"{c}_t"])
        merged = merged.drop(columns=[c for c in merged.columns if c.endswith("_t")])

    # enforce schema per horizon/model; keep as one long df
    out_parts = []
    for (model_name, horizon_type), g in merged.groupby(["model_name", "horizon_type"], dropna=False):
        raw = g[["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        out_parts.append(ensure_barangay_forecast_df(raw, model_name=str(model_name), horizon_type=str(horizon_type)))

    return pd.concat(out_parts, ignore_index=True) if out_parts else existing_long


def local_models_tierA(
    tierA: List[str],
    weekly_full: pd.DataFrame,
    test_city: pd.DataFrame,
    train_end: pd.Timestamp,
    horizon: int,
    PROPHET_OK: bool,
    cfg: Config,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    import pmdarima as pm
    from sklearn.metrics import mean_squared_error

    tierA = sorted(set(tierA))

    if horizon <= 0:
        raise ValueError("Horizon must be positive.")

    test_ds = pd.DatetimeIndex(pd.to_datetime(test_city["ds"], errors="raise")).sort_values()
    test_end = test_ds.max()
    last_obs = pd.to_datetime(weekly_full["WeekStart"], errors="coerce").max()
    if pd.isna(last_obs):
        raise ValueError("weekly_full['WeekStart'] contains only invalid dates.")

    # Backtest behavior (current): future starts after test_end.
    # Production behavior (G0.3 later): future should start after last_obs.
    start_future = test_end  # <-- keep current behavior for now
    future_ds = pd.date_range(start=start_future + pd.Timedelta(weeks=1), periods=horizon, freq="W-MON")


    local_results: List[Dict[str, Any]] = []
    long_parts: List[pd.DataFrame] = []

    for bgy in tierA:
        err_prophet = None
        err_arima = None

        df_full = (
            weekly_full.loc[weekly_full["Barangay_key"] == bgy, ["WeekStart", "Cases"]]
            .rename(columns={"WeekStart": "ds", "Cases": "y"})
            .copy()
        )
        df_full["ds"] = pd.to_datetime(df_full["ds"], errors="coerce")
        df_full["y"] = pd.to_numeric(df_full["y"], errors="coerce").fillna(0.0)
        df_full = df_full.dropna(subset=["ds"]).groupby("ds", as_index=False).agg({"y": "sum"}).sort_values("ds")

        if len(df_full) < 52:
            local_results.append(
                {
                    "Barangay_key": bgy,
                    "RMSE_local_prophet": np.inf,
                    "RMSE_local_arima": np.inf,
                    "Chosen": None,
                    "status": "insufficient_history",
                    "err_prophet": None,
                    "err_arima": None,
                }
            )
            continue

        df_train = df_full[df_full["ds"] <= train_end].reset_index(drop=True)
        if len(df_train) < 52:
            local_results.append(
                {
                    "Barangay_key": bgy,
                    "RMSE_local_prophet": np.inf,
                    "RMSE_local_arima": np.inf,
                    "Chosen": None,
                    "status": "insufficient_train_history",
                    "err_prophet": None,
                    "err_arima": None,
                }
            )
            continue

        y_true_test = df_full.set_index("ds").reindex(test_ds, fill_value=0.0)["y"].to_numpy(dtype=float)

        # Prophet
        rmse_p = np.inf
        if PROPHET_OK:
            try:
                from prophet import Prophet

                mp = Prophet(
                    yearly_seasonality=True,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    interval_width=0.8,
                )
                mp.fit(df_train[["ds", "y"]])

                fut = mp.make_future_dataframe(periods=len(test_ds) + horizon, freq="W-MON")
                fp = mp.predict(fut).set_index("ds").sort_index()

                p_test_df = fp.reindex(test_ds)
                p_fut_df = fp.reindex(future_ds)

                p_test = np.clip(p_test_df["yhat"].to_numpy(float), 0, None)
                p_fut = np.clip(p_fut_df["yhat"].to_numpy(float), 0, None)

                p_ci_test = None
                p_ci_fut = None
                if {"yhat_lower", "yhat_upper"}.issubset(p_test_df.columns):
                    p_ci_test = np.clip(p_test_df[["yhat_lower", "yhat_upper"]].to_numpy(float), 0, None)
                if {"yhat_lower", "yhat_upper"}.issubset(p_fut_df.columns):
                    p_ci_fut = np.clip(p_fut_df[["yhat_lower", "yhat_upper"]].to_numpy(float), 0, None)

                if np.isnan(p_test).any() or np.isnan(p_fut).any():
                    raise ValueError("Prophet produced NaN outputs.")

                rmse_p = float(np.sqrt(mean_squared_error(y_true_test, p_test)))

                raw_test = pd.DataFrame(
                    {"Barangay_key": bgy, "ds": test_ds, "yhat": p_test,
                     "yhat_lower": (p_ci_test[:, 0] if p_ci_test is not None else p_test),
                     "yhat_upper": (p_ci_test[:, 1] if p_ci_test is not None else p_test)}
                )
                raw_fut = pd.DataFrame(
                    {"Barangay_key": bgy, "ds": future_ds, "yhat": p_fut,
                     "yhat_lower": (p_ci_fut[:, 0] if p_ci_fut is not None else p_fut),
                     "yhat_upper": (p_ci_fut[:, 1] if p_ci_fut is not None else p_fut)}
                )
                long_parts.append(ensure_barangay_forecast_df(raw_test, model_name="local_prophet", horizon_type="test"))
                long_parts.append(ensure_barangay_forecast_df(raw_fut, model_name="local_prophet", horizon_type="future"))
            except Exception as e:
                err_prophet = repr(e)


        # ARIMA
        rmse_a = np.inf
        try:
            y_train = df_train.set_index("ds")["y"]
            y_train.index = pd.DatetimeIndex(y_train.index, freq="W-MON")

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*force_all_finite.*", category=FutureWarning)
                ma = pm.auto_arima(
                    y_train,
                    seasonal=True,
                    m=52,
                    stepwise=True,
                    suppress_warnings=True,
                    error_action="ignore",
                )

            try:
                pred_test, conf_test = ma.predict(n_periods=len(test_ds), return_conf_int=True, alpha=0.2)
                pred_full, conf_full = ma.predict(n_periods=len(test_ds) + horizon, return_conf_int=True, alpha=0.2)
                pred_fut = pred_full[-horizon:]
                conf_fut = conf_full[-horizon:]
                a_ci_test = np.asarray(conf_test, dtype=float)
                a_ci_fut = np.asarray(conf_fut, dtype=float)
            except Exception as e_conf:
                # conf_int failed, fallback to point forecasts
                pred_test = ma.predict(n_periods=len(test_ds))
                pred_fut = ma.predict(n_periods=len(test_ds) + horizon)[-horizon:]
                a_ci_test = None
                a_ci_fut = None


            a_test = np.clip(np.asarray(pred_test, dtype=float), 0, None)
            a_fut = np.clip(np.asarray(pred_fut, dtype=float), 0, None)
            rmse_a = float(np.sqrt(mean_squared_error(y_true_test, a_test)))

            raw_test = pd.DataFrame(
                {"Barangay_key": bgy, "ds": test_ds, "yhat": a_test,
                 "yhat_lower": (a_ci_test[:, 0] if a_ci_test is not None else a_test),
                 "yhat_upper": (a_ci_test[:, 1] if a_ci_test is not None else a_test)}
            )
            raw_fut = pd.DataFrame(
                {"Barangay_key": bgy, "ds": future_ds, "yhat": a_fut,
                 "yhat_lower": (a_ci_fut[:, 0] if a_ci_fut is not None else a_fut),
                 "yhat_upper": (a_ci_fut[:, 1] if a_ci_fut is not None else a_fut)}
            )
            long_parts.append(ensure_barangay_forecast_df(raw_test, model_name="local_arima", horizon_type="test"))
            long_parts.append(ensure_barangay_forecast_df(raw_fut, model_name="local_arima", horizon_type="future"))
        except Exception as e:
            err_arima = repr(e)


        chosen = None
        status = "ok"
        if not np.isfinite(rmse_p) and not np.isfinite(rmse_a):
            status = "both_failed"
        elif not np.isfinite(rmse_p):
            status = "prophet_failed"
        elif not np.isfinite(rmse_a):
            status = "arima_failed"
        else:
            status = "ok"

        chosen = None
        if np.isfinite(rmse_p) or np.isfinite(rmse_a):
            chosen = "local_prophet" if rmse_p <= rmse_a else "local_arima"

        local_results.append(
            {
                "Barangay_key": bgy,
                "RMSE_local_prophet": float(rmse_p),
                "RMSE_local_arima": float(rmse_a),
                "Chosen": chosen,
                "status": status,
                "err_prophet": err_prophet,
                "err_arima": err_arima,
            }
        )

    # -----------------------
    # BUILD OUTPUT DATAFRAMES
    # -----------------------
    local_results_df = pd.DataFrame(local_results)
    local_results_df["run_id"] = cfg.run_id
    local_results_df.to_csv(cfg.out / "local_model_performance.csv", index=False)

    existing = pd.concat(long_parts, ignore_index=True) if long_parts else pd.DataFrame(
        columns=["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]
    )

    local_forecasts_long_df = _pad_local_grid(
        tierA=tierA,
        test_ds=test_ds,
        future_ds=future_ds,
        existing_long=existing,
    )
    local_forecasts_long_df["run_id"] = cfg.run_id
    local_forecasts_long_df.to_csv(cfg.out / "barangay_local_forecasts_long.csv", index=False)

    return local_results_df, local_forecasts_long_df

