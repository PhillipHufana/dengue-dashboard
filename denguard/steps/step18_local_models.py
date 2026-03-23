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

def _smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true) + np.abs(y_pred) + eps
    return float(np.mean(2.0 * np.abs(y_pred - y_true) / denom))


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_pred - y_true)))


def _safe_float(x: Any) -> float:
    try:
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return float("nan")
        return v
    except Exception:
        return float("nan")


def _suppress_known_arima_warnings() -> None:
    warnings.filterwarnings("ignore", message=".*force_all_finite.*", category=FutureWarning)
    warnings.filterwarnings("ignore", message=".*ensure_all_finite.*", category=FutureWarning)
    warnings.filterwarnings(
        "ignore",
        message=".*Non-invertible starting MA parameters found.*",
        category=UserWarning,
    )



def _pad_local_grid(
    barangay_keys: List[str],
    test_ds: pd.DatetimeIndex,
    future_ds: pd.DatetimeIndex,
    existing_long: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ensures every barangay has rows for both local models for all ds
    in both test and future horizons. Missing rows are filled with yhat=0.
    """
    # Safety: ensure keys are unique + stable ordering
    barangay_keys = sorted(set(barangay_keys))
    models = ["local_prophet", "local_arima"]

    def _template(ds: pd.DatetimeIndex, horizon_type: str) -> pd.DataFrame:
        mi = pd.MultiIndex.from_product(
            [barangay_keys, ds, models],
            names=["Barangay_key", "ds", "model_name"]
        )
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
    if not ex.empty:
        ex["ds"] = pd.to_datetime(ex["ds"], errors="raise")
        ex = ex.drop_duplicates(subset=["Barangay_key", "ds", "model_name", "horizon_type"], keep="last")

    if ex.empty:
        merged = tmpl
    else:
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


def save_local_metrics_tables(
    weekly_full: pd.DataFrame,
    test_city: pd.DataFrame,
    disagg_test_df: pd.DataFrame,
    local_forecasts_long: pd.DataFrame,
    local_perf: pd.DataFrame,
    cfg: Config,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Save thesis-ready aggregate backtest metrics:
      - local_model_metrics.csv: aggregate metrics for disagg/local_prophet/local_arima
      - preferred_backtest_metrics.csv: aggregate metrics using the chosen model per barangay
    """
    test_ds = pd.DatetimeIndex(pd.to_datetime(test_city["ds"], errors="raise")).sort_values()
    all_keys = sorted(weekly_full["Barangay_key"].dropna().astype(str).unique().tolist())

    actual_all = (
        weekly_full.loc[:, ["Barangay_key", "WeekStart", "Cases"]]
        .rename(columns={"WeekStart": "ds", "Cases": "y"})
        .copy()
    )
    actual_all["ds"] = pd.to_datetime(actual_all["ds"], errors="coerce")
    actual_all["y"] = pd.to_numeric(actual_all["y"], errors="coerce").fillna(0.0)
    actual_all = (
        actual_all.dropna(subset=["ds"])
        .groupby(["Barangay_key", "ds"], as_index=False)["y"].sum()
    )

    grid = pd.MultiIndex.from_product([all_keys, test_ds], names=["Barangay_key", "ds"]).to_frame(index=False)
    actual_all = grid.merge(actual_all, on=["Barangay_key", "ds"], how="left")
    actual_all["y"] = pd.to_numeric(actual_all["y"], errors="coerce").fillna(0.0)

    def _metrics_for(
        pred_df: pd.DataFrame,
        model_name: str,
        allowed_keys: set[str] | None = None,
    ) -> dict[str, float | str | int]:
        actual = actual_all
        if allowed_keys is not None:
            actual = actual[actual["Barangay_key"].astype(str).isin(allowed_keys)].copy()
        if actual.empty:
            return {
                "model_name": model_name,
                "n_barangays": 0,
                "n_rows": 0,
                "coverage_rows": 0,
                "RMSE": float("nan"),
                "MAE": float("nan"),
                "sMAPE": float("nan"),
            }

        pred = pred_df.copy()
        pred["ds"] = pd.to_datetime(pred["ds"], errors="coerce")
        pred = pred.dropna(subset=["ds"])
        pred = pred.groupby(["Barangay_key", "ds"], as_index=False)["yhat"].last()
        merged = actual.merge(pred, on=["Barangay_key", "ds"], how="left")
        observed_pred = pd.to_numeric(merged["yhat"], errors="coerce")
        coverage_rows = int(observed_pred.notna().sum())
        merged["yhat"] = observed_pred.fillna(0.0).clip(lower=0)

        y_true = merged["y"].to_numpy(dtype=float)
        y_pred = merged["yhat"].to_numpy(dtype=float)

        rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
        mae = _mae(y_true, y_pred)
        smape = _smape(y_true, y_pred)
        return {
            "model_name": model_name,
            "n_barangays": int(actual["Barangay_key"].nunique()),
            "n_rows": int(len(merged)),
            "coverage_rows": coverage_rows,
            "RMSE": rmse,
            "MAE": mae,
            "sMAPE": smape,
        }

    disagg_test = disagg_test_df[disagg_test_df["horizon_type"] == "test"].copy()
    local_test = local_forecasts_long[local_forecasts_long["horizon_type"] == "test"].copy()

    metric_rows = [_metrics_for(disagg_test, "disagg")]
    prophet_keys = set(
        local_perf.loc[np.isfinite(pd.to_numeric(local_perf["RMSE_local_prophet"], errors="coerce")), "Barangay_key"]
        .astype(str)
        .tolist()
    )
    arima_keys = set(
        local_perf.loc[np.isfinite(pd.to_numeric(local_perf["RMSE_local_arima"], errors="coerce")), "Barangay_key"]
        .astype(str)
        .tolist()
    )
    metric_rows.append(
        _metrics_for(local_test[local_test["model_name"] == "local_prophet"].copy(), "local_prophet", allowed_keys=prophet_keys)
    )
    metric_rows.append(
        _metrics_for(local_test[local_test["model_name"] == "local_arima"].copy(), "local_arima", allowed_keys=arima_keys)
    )

    local_metrics_df = pd.DataFrame(metric_rows)
    local_metrics_df["run_id"] = cfg.run_id
    local_metrics_df.to_csv(cfg.out / "local_model_metrics.csv", index=False)

    chosen_map = local_perf.set_index("Barangay_key")["Chosen"].to_dict()

    chosen_local = local_test.copy()
    chosen_local["Chosen"] = chosen_local["Barangay_key"].map(chosen_map)
    chosen_local = chosen_local[chosen_local["model_name"] == chosen_local["Chosen"]].copy()

    chosen_disagg = disagg_test.copy()
    chosen_disagg["Chosen"] = chosen_disagg["Barangay_key"].map(chosen_map)
    chosen_disagg = chosen_disagg[chosen_disagg["Chosen"] == "disagg"].copy()

    preferred_test = pd.concat(
        [
            chosen_disagg[["Barangay_key", "ds", "yhat"]],
            chosen_local[["Barangay_key", "ds", "yhat"]],
        ],
        ignore_index=True,
    )

    preferred_metrics_row = _metrics_for(preferred_test, "preferred_selected")
    preferred_metrics_row["chosen_disagg_barangays"] = int((local_perf["Chosen"] == "disagg").sum())
    preferred_metrics_row["chosen_local_prophet_barangays"] = int((local_perf["Chosen"] == "local_prophet").sum())
    preferred_metrics_row["chosen_local_arima_barangays"] = int((local_perf["Chosen"] == "local_arima").sum())

    preferred_metrics_df = pd.DataFrame([preferred_metrics_row])
    preferred_metrics_df["run_id"] = cfg.run_id
    preferred_metrics_df.to_csv(cfg.out / "preferred_backtest_metrics.csv", index=False)

    return local_metrics_df, preferred_metrics_df


def local_models_tierA(
    barangay_keys: List[str],
    eligible_keys: List[str],
    weekly_full: pd.DataFrame,
    test_city: pd.DataFrame,
    train_end: pd.Timestamp,
    horizon: int,
    PROPHET_OK: bool,
    cfg: Config,
    *,
    disagg_test_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    import pmdarima as pm
    from sklearn.metrics import mean_squared_error


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
    arima_order_rows: List[Dict[str, Any]] = []

    all_keys = sorted(set(barangay_keys))
    eligible_set = set(eligible_keys)

    min_train_weeks = int(getattr(cfg, "local_min_train_weeks", 104))


    for bgy in all_keys:
        if bgy not in eligible_set:
            local_results.append({
                "Barangay_key": bgy,
                "RMSE_local_prophet": np.inf,
                "MAE_local_prophet": np.inf,
                "RMSE_local_arima": np.inf,
                "MAE_local_arima": np.inf,
                "RMSE_disagg_test": np.inf,
                "MAE_disagg_test": np.inf,
                "sMAPE_local_prophet_test": float("inf"),
                "sMAPE_local_arima_test": float("inf"),
                "sMAPE_disagg_test": float("inf"),
                "sMAPE_best_local_test": float("inf"),
                "delta_disagg_minus_local": float("nan"),
                "best_local_model": None,
                "Chosen": "disagg",
                "decision_reason": "ineligible_data_sufficiency",
                "status": "ineligible",
                "err_prophet": None,
                "err_arima": None,
            })
            continue

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


        df_train = df_full[df_full["ds"] <= train_end].reset_index(drop=True)

        #  force weekly grid so local models train on consistent W-MON
        df_train = (
            df_train.set_index("ds")
            .asfreq("W-MON")
            .fillna({"y": 0.0})
            .reset_index()
        )

        if len(df_train) < min_train_weeks:
            local_results.append(
                {
                    "Barangay_key": bgy,
                    "RMSE_local_prophet": np.inf,
                    "MAE_local_prophet": np.inf,
                    "RMSE_local_arima": np.inf,
                    "MAE_local_arima": np.inf,
                    "RMSE_disagg_test": np.inf,
                    "MAE_disagg_test": np.inf,
                    "sMAPE_local_prophet_test": float("inf"),
                    "sMAPE_local_arima_test": float("inf"),
                    "sMAPE_disagg_test": float("inf"),
                    "sMAPE_best_local_test": float("inf"),
                    "delta_disagg_minus_local": float("nan"),
                    "best_local_model": None,
                    "Chosen": "disagg",
                    "status": "insufficient_train_history",
                    "decision_reason": "insufficient_train_history_default_disagg",
                    "err_prophet": None,
                    "err_arima": None,
                }
            )
            continue

        y_true_test = (
            weekly_full.loc[weekly_full["Barangay_key"] == bgy, ["WeekStart", "Cases"]]
            .rename(columns={"WeekStart": "ds", "Cases": "y"})
            .assign(ds=lambda d: pd.to_datetime(d["ds"], errors="coerce"),
                    y=lambda d: pd.to_numeric(d["y"], errors="coerce").fillna(0.0))
            .dropna(subset=["ds"])
            .groupby("ds", as_index=False)["y"].sum()
            .set_index("ds")
            .reindex(test_ds, fill_value=0.0)["y"]
            .to_numpy(dtype=float)
        )


        # ----------------------------
        # Disagg baseline (Choice A) 
        # ----------------------------
        rmse_disagg = np.inf
        mae_disagg = np.inf
        smape_disagg = float("inf")
        

        try:
            dis_bgy = disagg_test_df[
                (disagg_test_df["Barangay_key"] == bgy) &
                (disagg_test_df["horizon_type"] == "test")
            ].copy()
            if not dis_bgy.empty:
                dis_bgy["ds"] = pd.to_datetime(dis_bgy["ds"], errors="raise")
                dis_bgy = dis_bgy.set_index("ds").sort_index()
                dis_pred = dis_bgy.reindex(test_ds, fill_value=0.0)["yhat"].to_numpy(dtype=float)
                dis_pred = np.clip(dis_pred, 0, None)
                rmse_disagg = float(np.sqrt(mean_squared_error(y_true_test, dis_pred)))
                mae_disagg = _mae(y_true_test, dis_pred)
                smape_disagg = _smape(y_true_test, dis_pred)
                
        except Exception:
            rmse_disagg = np.inf
            mae_disagg = np.inf
            smape_disagg = float("inf")
        
        disagg_available = np.isfinite(smape_disagg)


        # Prophet
        smape_p = float("inf")
        rmse_p = np.inf
        mae_p = np.inf
        if PROPHET_OK:

            try:
                from prophet import Prophet

                mp = Prophet(
                    yearly_seasonality=True,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    changepoint_prior_scale=0.05,
                    seasonality_mode="additive",
                    interval_width=0.95,
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
                mae_p = _mae(y_true_test, p_test)
                smape_p = _smape(y_true_test, p_test)


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
        smape_a = float("inf")
        rmse_a = np.inf
        mae_a = np.inf
        try:
            y_train = df_train.set_index("ds")["y"].sort_index()
            y_train.index = pd.DatetimeIndex(y_train.index)
            y_train = y_train.asfreq("W-MON").fillna(0.0)


            with warnings.catch_warnings():
                _suppress_known_arima_warnings()
                ma = pm.auto_arima(
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

            with warnings.catch_warnings():
                _suppress_known_arima_warnings()
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
            mae_a = _mae(y_true_test, a_test)
            smape_a = _smape(y_true_test, a_test)
            order = tuple(getattr(ma, "order", (None, None, None)))
            seasonal_order = tuple(getattr(ma, "seasonal_order", (0, 0, 0, 0)))
            arima_order_rows.append(
                {
                    "model_name": "arima",
                    "model_scope": "local",
                    "unit_key": str(bgy),
                    "order_label": str(order),
                    "order_p": order[0],
                    "order_d": order[1],
                    "order_q": order[2],
                    "seasonal": False,
                    "seasonal_period": 1,
                    "seasonal_P": seasonal_order[0],
                    "seasonal_D": seasonal_order[1],
                    "seasonal_Q": seasonal_order[2],
                }
            )

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


        # ----------------------------
        # Choice A decision (sMAPE)
        # local only if it beats disagg by margin
        # ----------------------------
        margin = float(getattr(cfg, "local_vs_disagg_smape_margin", 0.03))

        status = "ok"
        if not np.isfinite(rmse_p) and not np.isfinite(rmse_a):
            status = "both_failed"
        elif not np.isfinite(rmse_p):
            status = "prophet_failed"
        elif not np.isfinite(rmse_a):
            status = "arima_failed"

        best_local_model = None
        smape_best_local = float("inf")
        if np.isfinite(smape_p) or np.isfinite(smape_a):
            if smape_p <= smape_a:
                best_local_model = "local_prophet"
                smape_best_local = smape_p
            else:
                best_local_model = "local_arima"
                smape_best_local = smape_a

        # Default to disagg if local doesn't clearly win
        chosen = "disagg"
        decision_reason = (
            f"default_disagg_or_local_not_better_by_margin({margin:.2f})"
            if disagg_available else "disagg_baseline_missing_default_disagg"
        )

        delta = np.nan

        if np.isfinite(smape_disagg) and np.isfinite(smape_best_local):
            delta = float(smape_disagg - smape_best_local)
            if smape_best_local <= (smape_disagg - margin):
                chosen = str(best_local_model)
                decision_reason = f"local_beats_disagg_by_margin({margin:.2f})"

        local_results.append(
            {
                "Barangay_key": bgy,
                "RMSE_local_prophet": float(rmse_p),
                "MAE_local_prophet": float(mae_p),
                "RMSE_local_arima": float(rmse_a),
                "MAE_local_arima": float(mae_a),
                "RMSE_disagg_test": float(rmse_disagg),
                "MAE_disagg_test": float(mae_disagg),
                "sMAPE_local_prophet_test": float(smape_p),
                "sMAPE_local_arima_test": float(smape_a),
                "sMAPE_disagg_test": float(smape_disagg),
                "sMAPE_best_local_test": float(smape_best_local),
                "delta_disagg_minus_local": _safe_float(delta),
                "best_local_model": best_local_model,
                "Chosen": chosen,  #  now: local_prophet/local_arima/disagg
                "decision_reason": decision_reason,
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
        barangay_keys=all_keys,
        test_ds=test_ds,
        future_ds=future_ds,
        existing_long=existing,
    )
    local_forecasts_long_df["run_id"] = cfg.run_id
    local_forecasts_long_df.to_csv(cfg.out / "barangay_local_forecasts_long.csv", index=False)

    arima_orders_df = pd.DataFrame(arima_order_rows)
    if not arima_orders_df.empty:
        arima_orders_df["run_id"] = cfg.run_id

    return local_results_df, local_forecasts_long_df, arima_orders_df

