# ============================================================
# file: denguard/run_pipeline.py
# (PATCHED) fix wiring for standardized forecasts
# ============================================================
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pandas as pd

from denguard.config import DEFAULT_CFG, Config
from denguard.export_supabase import upload_to_supabase
from denguard.horizon import resolve_horizon
from denguard.selection import select_city_model
from denguard.steps.step10_disagg import hybrid_disaggregation
from denguard.steps.step11_prophet_diag import prophet_additional_diagnostics
from denguard.steps.step12_plot_sample import plot_sample_barangays
from denguard.steps.step13_errors import barangay_error_ranking
from denguard.steps.step15_prophet_cv import prophet_cross_validation
from denguard.steps.step16_health import model_health_report
from denguard.steps.step19_reconcile import reconcile_forecasts
from denguard.steps.step1_load_clean import finalize_ingestion_registry, load_and_clean, persist_clean
from denguard.steps.step24_incremental_filter import incremental_filter
from denguard.steps.step25_fingerprint_dedupe import fingerprint_dedupe
from denguard.steps.step2_standardize import standardize_barangays
from denguard.steps.step3_validation import validation_summary
from denguard.steps.step4_weekly_agg import weekly_aggregation
from denguard.steps.step5_city_series import build_city_series
from denguard.steps.step6_split import train_test_split_city
from denguard.steps.step7_prophet import fit_prophet
from denguard.steps.step8_arima import fit_arima
from denguard.steps.step9_comparison import comparison_plot
from denguard.utils import ensure_outdir


def _init_run(cfg: Config) -> Config:
    ensure_outdir(cfg.out)
    run_id = cfg.run_id or str(uuid4())
    started_at = cfg.run_started_at_utc or datetime.now(timezone.utc).isoformat()
    cfg = replace(cfg, run_id=run_id, run_started_at_utc=started_at)

    run_row = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "run_started_at_utc": started_at,
                "run_kind": getattr(cfg, "run_kind", "backtest"),
                "backtest_end_date": getattr(cfg, "backtest_end_date", None),
                "incoming_mode": cfg.incoming_mode,
                "forecast_weeks_override": cfg.forecast_weeks_override,
            }
        ]
    )
    run_row.to_csv(cfg.out / "runs.csv", mode="a", header=not (cfg.out / "runs.csv").exists(), index=False)
    print(f"run_id = {run_id} | run_kind = {getattr(cfg, 'run_kind', 'backtest')}")
    return cfg


def _require_backtest(cfg: Config, step_name: str) -> None:
    if getattr(cfg, "run_kind", "backtest") != "backtest":
        raise RuntimeError(
            f"{step_name} is backtest-only (needs a non-empty test window + disagg_test baseline). "
            f"Current run_kind={getattr(cfg, 'run_kind', None)}."
        )


def _save_city_metrics_table(cfg: Config, metrics_prophet: dict, metrics_arima: dict) -> pd.DataFrame:
    city_metrics_df = pd.DataFrame(
        [
            {
                "model_name": "prophet",
                "RMSE": float(metrics_prophet.get("RMSE", float("nan"))),
                "MAE": float(metrics_prophet.get("MAE", float("nan"))),
                "sMAPE": float(metrics_prophet.get("sMAPE", float("nan"))),
            },
            {
                "model_name": "arima",
                "RMSE": float(metrics_arima.get("RMSE", float("nan"))),
                "MAE": float(metrics_arima.get("MAE", float("nan"))),
                "sMAPE": float(metrics_arima.get("sMAPE", float("nan"))),
            },
        ]
    )
    city_metrics_df["run_id"] = cfg.run_id
    city_metrics_df.to_csv(cfg.out / "city_model_metrics.csv", index=False)
    return city_metrics_df


def _safe_date(series: pd.Series) -> str | None:
    if series is None or len(series) == 0:
        return None
    dt = pd.to_datetime(series, errors="coerce").dropna()
    if dt.empty:
        return None
    return dt.iloc[0].date().isoformat()


def _save_run_metadata(
    cfg: Config,
    *,
    city_weekly: pd.DataFrame,
    train_city: pd.DataFrame,
    test_city: pd.DataFrame,
    forecast_horizon_weeks: int,
    selected_primary_model: str,
    alpha_smooth: float,
) -> pd.DataFrame:
    city_date_col = "ds" if "ds" in city_weekly.columns else "WeekStart"
    data_cutoff = pd.to_datetime(city_weekly[city_date_col], errors="coerce").dropna()
    train_ds = pd.to_datetime(train_city["ds"], errors="coerce").dropna()
    test_ds = pd.to_datetime(test_city["ds"], errors="coerce").dropna() if not test_city.empty else pd.Series(dtype="datetime64[ns]")

    row = pd.DataFrame(
        [
            {
                "run_id": cfg.run_id,
                "run_kind": getattr(cfg, "run_kind", "backtest"),
                "data_cutoff_date": data_cutoff.max().date().isoformat() if not data_cutoff.empty else None,
                "train_start": train_ds.min().date().isoformat() if not train_ds.empty else None,
                "train_end": train_ds.max().date().isoformat() if not train_ds.empty else None,
                "test_start": test_ds.min().date().isoformat() if not test_ds.empty else None,
                "test_end": test_ds.max().date().isoformat() if not test_ds.empty else None,
                "test_length_weeks": int(len(test_city)),
                "forecast_horizon_weeks": int(forecast_horizon_weeks),
                "disagg_weight_weeks": int(getattr(cfg, "disagg_weight_weeks", 52)),
                "alpha_smooth": float(alpha_smooth),
                "selected_primary_model": str(selected_primary_model),
                "incoming_mode": cfg.incoming_mode,
                "backtest_end_date": getattr(cfg, "backtest_end_date", None),
            }
        ]
    )
    row.to_csv(cfg.out / "run_metadata.csv", index=False)
    return row


def _build_city_arima_future(
    *,
    model_arima: object,
    train_city: pd.DataFrame,
    test_city: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    if model_arima is None:
        raise RuntimeError("ARIMA model is None.")

    train_ds = pd.to_datetime(train_city["ds"], errors="raise")
    if not test_city.empty:
        last_obs_ds = pd.to_datetime(pd.concat([train_city["ds"], test_city["ds"]]), errors="raise").max()
        test_len = int(len(test_city))
    else:
        last_obs_ds = train_ds.max()
        test_len = 0

    future_dates = pd.date_range(last_obs_ds + pd.Timedelta(weeks=1), periods=int(horizon), freq="W-MON")
    total_periods = int(test_len) + int(horizon)
    preds_full, conf = model_arima.predict(n_periods=total_periods, return_conf_int=True, alpha=0.2)
    preds_full = np.asarray(preds_full, dtype=float)
    conf = np.asarray(conf, dtype=float)
    preds_future = preds_full[test_len:]
    conf_future = conf[test_len:]
    out = pd.DataFrame(
        {
            "ds": future_dates,
            "yhat": preds_future,
            "yhat_lower": conf_future[:, 0],
            "yhat_upper": conf_future[:, 1],
            "model_name": "arima",
            "horizon_type": "future",
        }
    )
    return out


def _save_city_backtest_predictions(
    cfg: Config,
    *,
    test_city: pd.DataFrame,
    city_prophet_test: pd.DataFrame,
    city_arima_test: pd.DataFrame,
) -> pd.DataFrame:
    base = test_city.copy()
    base["ds"] = pd.to_datetime(base["ds"], errors="raise")
    base = base.rename(columns={"y": "y_true"})[["ds", "y_true"]]

    prophet = city_prophet_test.copy().rename(
        columns={
            "yhat": "yhat_prophet",
            "yhat_lower": "yhat_lower_prophet",
            "yhat_upper": "yhat_upper_prophet",
        }
    )[["ds", "yhat_prophet", "yhat_lower_prophet", "yhat_upper_prophet"]]
    arima = city_arima_test.copy().rename(
        columns={
            "yhat": "yhat_arima",
            "yhat_lower": "yhat_lower_arima",
            "yhat_upper": "yhat_upper_arima",
        }
    )[["ds", "yhat_arima", "yhat_lower_arima", "yhat_upper_arima"]]

    out = base.merge(prophet, on="ds", how="left").merge(arima, on="ds", how="left")
    out["run_id"] = cfg.run_id
    out = out[
        [
            "run_id",
            "ds",
            "y_true",
            "yhat_prophet",
            "yhat_lower_prophet",
            "yhat_upper_prophet",
            "yhat_arima",
            "yhat_lower_arima",
            "yhat_upper_arima",
        ]
    ]
    out.to_csv(cfg.out / "city_backtest_predictions_long.csv", index=False)
    return out


def _save_barangay_backtest_predictions(
    cfg: Config,
    *,
    weekly_full: pd.DataFrame,
    test_city: pd.DataFrame,
    bg_backtest_long: pd.DataFrame,
) -> pd.DataFrame:
    if bg_backtest_long.empty:
        cols = ["run_id", "ds", "barangay", "y_true", "method", "yhat", "yhat_lower", "yhat_upper"]
        out = pd.DataFrame(columns=cols)
        out.to_csv(cfg.out / "barangay_backtest_predictions_long.csv", index=False)
        return out

    test_dates = pd.to_datetime(test_city["ds"], errors="coerce").dropna().unique()
    actuals = weekly_full.copy()
    actuals["ds"] = pd.to_datetime(actuals["WeekStart"], errors="coerce")
    actuals = actuals[actuals["ds"].isin(test_dates)].copy()
    actuals = actuals.rename(columns={"Barangay_key": "barangay", "Cases": "y_true"})
    actuals = actuals[["barangay", "ds", "y_true"]]

    preds = bg_backtest_long.copy()
    preds["ds"] = pd.to_datetime(preds["ds"], errors="coerce")
    preds = preds.rename(columns={"Barangay_key": "barangay"})
    method_col = "method" if "method" in preds.columns else "model_name"
    preds = preds[["barangay", "ds", method_col, "yhat", "yhat_lower", "yhat_upper"]].rename(columns={method_col: "method"})

    out = actuals.merge(preds, on=["barangay", "ds"], how="inner")
    out["run_id"] = cfg.run_id
    out = out[["run_id", "ds", "barangay", "y_true", "method", "yhat", "yhat_lower", "yhat_upper"]]
    out.to_csv(cfg.out / "barangay_backtest_predictions_long.csv", index=False)
    return out


def _save_coherence_check(
    cfg: Config,
    *,
    city_df: pd.DataFrame,
    barangay_df: pd.DataFrame,
    method: str,
    filename: str,
) -> pd.DataFrame:
    if barangay_df.empty or city_df.empty:
        out = pd.DataFrame(columns=["run_id", "ds", "method", "city_yhat", "sum_barangay_yhat", "diff"])
        out.to_csv(cfg.out / filename, index=False)
        return out

    city = city_df.copy()
    city["ds"] = pd.to_datetime(city["ds"], errors="coerce")
    city = city[["ds", "yhat"]].rename(columns={"yhat": "city_yhat"})

    bg = barangay_df.copy()
    bg["ds"] = pd.to_datetime(bg["ds"], errors="coerce")
    bg = bg.groupby("ds", as_index=False)["yhat"].sum().rename(columns={"yhat": "sum_barangay_yhat"})

    out = city.merge(bg, on="ds", how="left")
    out["sum_barangay_yhat"] = pd.to_numeric(out["sum_barangay_yhat"], errors="coerce").fillna(0.0)
    out["diff"] = out["sum_barangay_yhat"] - out["city_yhat"]
    out["method"] = str(method)
    out["run_id"] = cfg.run_id
    out = out[["run_id", "ds", "method", "city_yhat", "sum_barangay_yhat", "diff"]]
    out.to_csv(cfg.out / filename, index=False)
    return out


def _save_multi_method_coherence(
    cfg: Config,
    *,
    city_long_df: pd.DataFrame,
    barangay_long_df: pd.DataFrame,
    filename: str,
    horizon_type: str,
) -> pd.DataFrame:
    if city_long_df.empty or barangay_long_df.empty:
        out = pd.DataFrame(columns=["run_id", "ds", "method", "city_yhat", "sum_barangay_yhat", "diff"])
        out.to_csv(cfg.out / filename, index=False)
        return out

    city = city_long_df.copy()
    city = city[city["horizon_type"] == horizon_type].copy()
    city["ds"] = pd.to_datetime(city["ds"], errors="coerce")
    city = city.rename(columns={"model_name": "method", "yhat": "city_yhat"})[["ds", "method", "city_yhat"]]

    bg = barangay_long_df.copy()
    bg = bg[bg["horizon_type"] == horizon_type].copy()
    bg["ds"] = pd.to_datetime(bg["ds"], errors="coerce")
    method_col = "method" if "method" in bg.columns else "model_name"
    bg = (
        bg.groupby(["ds", method_col], as_index=False)["yhat"]
        .sum()
        .rename(columns={method_col: "method", "yhat": "sum_barangay_yhat"})
    )

    out = city.merge(bg, on=["ds", "method"], how="left")
    out["sum_barangay_yhat"] = pd.to_numeric(out["sum_barangay_yhat"], errors="coerce").fillna(0.0)
    out["diff"] = out["sum_barangay_yhat"] - out["city_yhat"]
    out["run_id"] = cfg.run_id
    out = out[["run_id", "ds", "method", "city_yhat", "sum_barangay_yhat", "diff"]]
    out.to_csv(cfg.out / filename, index=False)
    return out


def _smape(y_true: pd.Series, yhat: pd.Series) -> float:
    yt = pd.to_numeric(y_true, errors="coerce").fillna(0.0).astype(float)
    yp = pd.to_numeric(yhat, errors="coerce").fillna(0.0).astype(float)
    denom = yt.abs() + yp.abs()
    mask = denom > 0
    if not mask.any():
        return 0.0
    return float((2.0 * (yt[mask] - yp[mask]).abs() / denom[mask]).mean())


def _save_barangay_metric_distribution(
    cfg: Config,
    *,
    barangay_backtest_df: pd.DataFrame,
) -> pd.DataFrame:
    if barangay_backtest_df.empty:
        out = pd.DataFrame(
            columns=[
                "run_id",
                "method",
                "median_mae",
                "mae_p25",
                "mae_p75",
                "mae_iqr",
                "mae_p90",
                "pct_barangays_mae_lt_1",
                "pct_barangays_mae_lt_2",
                "median_smape",
                "smape_p25",
                "smape_p75",
            ]
        )
        out.to_csv(cfg.out / "barangay_metric_distribution.csv", index=False)
        return out

    df = barangay_backtest_df.copy()
    df["y_true"] = pd.to_numeric(df["y_true"], errors="coerce").fillna(0.0)
    df["yhat"] = pd.to_numeric(df["yhat"], errors="coerce").fillna(0.0)

    per_barangay = []
    for (method, barangay), grp in df.groupby(["method", "barangay"], dropna=False):
        err = grp["y_true"] - grp["yhat"]
        mae = float(err.abs().mean())
        rmse = float(np.sqrt((err**2).mean()))
        smape = _smape(grp["y_true"], grp["yhat"])
        per_barangay.append(
            {
                "method": method,
                "barangay": barangay,
                "MAE": mae,
                "RMSE": rmse,
                "sMAPE": smape,
            }
        )

    per_df = pd.DataFrame(per_barangay)
    rows = []
    for method, grp in per_df.groupby("method", dropna=False):
        p25 = float(grp["MAE"].quantile(0.25))
        p75 = float(grp["MAE"].quantile(0.75))
        rows.append(
            {
                "run_id": cfg.run_id,
                "method": method,
                "median_mae": float(grp["MAE"].median()),
                "mae_p25": p25,
                "mae_p75": p75,
                "mae_iqr": p75 - p25,
                "mae_p90": float(grp["MAE"].quantile(0.90)),
                "pct_barangays_mae_lt_1": float((grp["MAE"] < 1.0).mean()),
                "pct_barangays_mae_lt_2": float((grp["MAE"] < 2.0).mean()),
                "median_smape": float(grp["sMAPE"].median()),
                "smape_p25": float(grp["sMAPE"].quantile(0.25)),
                "smape_p75": float(grp["sMAPE"].quantile(0.75)),
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(cfg.out / "barangay_metric_distribution.csv", index=False)
    return out


def _save_barangay_risk_scores(
    cfg: Config,
    *,
    weekly_full: pd.DataFrame,
    bg_future: pd.DataFrame,
    epsilon: float = 1.0,
) -> pd.DataFrame:
    if bg_future.empty:
        out = pd.DataFrame(
            columns=["run_id", "barangay", "current_burden", "past_8w_avg", "forecast_burden", "surge_score", "method"]
        )
        out.to_csv(cfg.out / "barangay_risk_scores.csv", index=False)
        return out

    future = bg_future.copy()
    future["ds"] = pd.to_datetime(future["ds"], errors="coerce")
    forecast_start = future["ds"].min()
    future_4w_end = forecast_start + pd.Timedelta(weeks=3)
    method_col = "method" if "method" in future.columns else "model_name"

    hist = weekly_full.copy()
    hist["ds"] = pd.to_datetime(hist["WeekStart"], errors="coerce")
    hist = hist[hist["ds"] < forecast_start].copy()

    last_4_start = forecast_start - pd.Timedelta(weeks=4)
    last_8_start = forecast_start - pd.Timedelta(weeks=8)

    current_4w = (
        hist[(hist["ds"] >= last_4_start) & (hist["ds"] < forecast_start)]
        .groupby("Barangay_key", as_index=False)["Cases"]
        .sum()
        .rename(columns={"Barangay_key": "barangay", "Cases": "current_burden"})
    )
    past_8w = (
        hist[(hist["ds"] >= last_8_start) & (hist["ds"] < forecast_start)]
        .groupby("Barangay_key", as_index=False)["Cases"]
        .mean()
        .rename(columns={"Barangay_key": "barangay", "Cases": "past_8w_avg"})
    )
    forecast_4w = (
        future[(future["ds"] >= forecast_start) & (future["ds"] <= future_4w_end)]
        .groupby(["Barangay_key", method_col], as_index=False)["yhat"]
        .sum()
        .rename(columns={"Barangay_key": "barangay", method_col: "method", "yhat": "forecast_burden"})
    )

    canonical = pd.read_csv(cfg.canon_csv)
    all_keys = pd.Series(canonical["canonical_name"]).astype(str)
    from denguard.keys import make_barangay_db_key
    methods = sorted(map(str, pd.Series(future[method_col]).dropna().unique().tolist()))
    base = pd.MultiIndex.from_product(
        [all_keys.map(make_barangay_db_key).dropna().unique(), methods], names=["barangay", "method"]
    ).to_frame(index=False)

    out = base.merge(current_4w, on="barangay", how="left")
    out = out.merge(past_8w, on="barangay", how="left")
    out = out.merge(forecast_4w, on=["barangay", "method"], how="left")
    for col in ["current_burden", "past_8w_avg", "forecast_burden"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    out["surge_score"] = out["forecast_burden"] / (out["past_8w_avg"] + float(epsilon))
    out["run_id"] = cfg.run_id
    out = out[["run_id", "barangay", "current_burden", "past_8w_avg", "forecast_burden", "surge_score", "method"]]
    out.to_csv(cfg.out / "barangay_risk_scores.csv", index=False)
    return out


def _tag_barangay_method(df: pd.DataFrame, method: str) -> pd.DataFrame:
    out = df.copy()
    out["model_name"] = str(method)
    out["method"] = str(method)
    return out


def _build_barangay_all_models_future(
    cfg: Config,
    *,
    prophet_future: pd.DataFrame,
    arima_future: pd.DataFrame,
    preferred_future: pd.DataFrame,
) -> pd.DataFrame:
    from denguard.keys import make_barangay_db_key
    from denguard.forecast_schema import ensure_barangay_forecast_long_df

    canonical = pd.read_csv(cfg.canon_csv)
    all_keys = canonical["canonical_name"].map(make_barangay_db_key).dropna().unique()
    all_ds = pd.DatetimeIndex(pd.to_datetime(preferred_future["ds"], errors="raise")).sort_values().unique()
    model_list = ["prophet", "arima", "preferred"]

    grid = (
        pd.MultiIndex.from_product([all_keys, all_ds, model_list], names=["Barangay_key", "ds", "model_name"])
        .to_frame(index=False)
    )
    grid["horizon_type"] = "future"

    frames = [
        prophet_future[["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]].copy(),
        arima_future[["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]].copy(),
        preferred_future[["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]].copy(),
    ]
    combined = pd.concat(frames, ignore_index=True)
    combined["ds"] = pd.to_datetime(combined["ds"], errors="raise")
    combined = combined.drop_duplicates(
        subset=["Barangay_key", "ds", "model_name", "horizon_type"],
        keep="last",
    ).copy()
    out = grid.merge(combined, on=["Barangay_key", "ds", "model_name", "horizon_type"], how="left")
    missing_mask = out["yhat"].isna()
    for c in ["yhat", "yhat_lower", "yhat_upper"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0).clip(lower=0)
    out["status"] = np.where(missing_mask, "filled", "ok")
    out = out.drop_duplicates(
        subset=["Barangay_key", "ds", "model_name", "horizon_type"],
        keep="last",
    ).copy()
    out = ensure_barangay_forecast_long_df(out)
    out["run_id"] = cfg.run_id
    return out.sort_values(["Barangay_key", "model_name", "ds"]).reset_index(drop=True)


def _save_model_failure_summary(
    cfg: Config,
    *,
    run_kind: str,
    prophet_ok: bool,
    arima_ok: bool,
    local_summary_df: pd.DataFrame,
) -> pd.DataFrame:
    city_rows = pd.DataFrame(
        [
            {
                "model_scope": "city",
                "model_name": "prophet",
                "attempted_units": 1,
                "successful_units": int(bool(prophet_ok)),
                "failed_units": int(not bool(prophet_ok)),
            },
            {
                "model_scope": "city",
                "model_name": "arima",
                "attempted_units": 1,
                "successful_units": int(bool(arima_ok)),
                "failed_units": int(not bool(arima_ok)),
            },
        ]
    )
    city_rows["failure_rate"] = city_rows["failed_units"] / city_rows["attempted_units"]

    out = pd.concat([city_rows, local_summary_df.copy()], ignore_index=True)
    out["run_id"] = cfg.run_id
    out["run_kind"] = run_kind
    out.to_csv(cfg.out / "model_failure_summary.csv", index=False)
    out.to_csv(
        cfg.out / "model_failure_summary_by_run.csv",
        mode="a",
        header=not (cfg.out / "model_failure_summary_by_run.csv").exists(),
        index=False,
    )
    return out


def _save_arima_selected_orders(
    cfg: Config,
    *,
    city_model_arima: object,
    local_orders_df: pd.DataFrame | None,
    run_kind: str,
) -> pd.DataFrame:
    city_order = tuple(getattr(city_model_arima, "order", (None, None, None)))
    city_seasonal_order = tuple(getattr(city_model_arima, "seasonal_order", (0, 0, 0, 0)))
    city_row = pd.DataFrame(
        [
            {
                "model_name": "arima",
                "model_scope": "city",
                "unit_key": "city",
                "order_label": str(city_order),
                "order_p": city_order[0],
                "order_d": city_order[1],
                "order_q": city_order[2],
                "seasonal": False,
                "seasonal_period": 1,
                "seasonal_P": city_seasonal_order[0],
                "seasonal_D": city_seasonal_order[1],
                "seasonal_Q": city_seasonal_order[2],
            }
        ]
    )

    frames = [city_row]
    if local_orders_df is not None and not local_orders_df.empty:
        frames.append(local_orders_df.copy())

    out = pd.concat(frames, ignore_index=True)
    out["run_id"] = cfg.run_id
    out["run_kind"] = run_kind
    out.to_csv(cfg.out / "arima_selected_orders.csv", index=False)
    return out


def _build_disagg_only_policy(cfg: Config, barangay_keys: list[str]) -> pd.DataFrame:
    rows = []
    for key in sorted(map(str, barangay_keys)):
        rows.append(
            {
                "Barangay_key": key,
                "RMSE_local_prophet": float("nan"),
                "MAE_local_prophet": float("nan"),
                "RMSE_local_arima": float("nan"),
                "MAE_local_arima": float("nan"),
                "RMSE_disagg_test": float("nan"),
                "MAE_disagg_test": float("nan"),
                "sMAPE_local_prophet_test": float("nan"),
                "sMAPE_local_arima_test": float("nan"),
                "sMAPE_disagg_test": float("nan"),
                "sMAPE_best_local_test": float("nan"),
                "delta_disagg_minus_local": float("nan"),
                "best_local_model": None,
                "Chosen": "disagg",
                "decision_reason": "local_models_disabled",
                "status": "disabled",
                "err_prophet": None,
                "err_arima": None,
            }
        )

    policy_df = pd.DataFrame(rows)
    policy_df["run_id"] = cfg.run_id
    policy_df.to_csv(cfg.out / "local_model_performance.csv", index=False)

    eligibility_df = pd.DataFrame(
        {
            "Barangay_key": [str(k) for k in sorted(map(str, barangay_keys))],
            "train_weeks": np.nan,
            "nonzero_weeks": np.nan,
            "total_cases": np.nan,
            "eligible_local": False,
            "eligibility_reason": "local_models_disabled",
            "run_id": cfg.run_id,
        }
    )
    eligibility_df.to_csv(cfg.out / "local_eligibility.csv", index=False)
    return policy_df


def _empty_local_forecasts(cfg: Config) -> pd.DataFrame:
    cols = ["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type", "run_id"]
    empty_df = pd.DataFrame(columns=cols)
    empty_df.to_csv(cfg.out / "barangay_local_forecasts_long.csv", index=False)
    return empty_df


def _disabled_local_failure_summary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "model_scope": "local",
                "model_name": "local_prophet",
                "attempted_units": 0,
                "successful_units": 0,
                "failed_units": 0,
                "failure_rate": 0.0,
            },
            {
                "model_scope": "local",
                "model_name": "local_arima",
                "attempted_units": 0,
                "successful_units": 0,
                "failed_units": 0,
                "failure_rate": 0.0,
            },
        ]
    )


def _save_disagg_only_backtest_metrics(
    cfg: Config,
    *,
    weekly_full: pd.DataFrame,
    test_city: pd.DataFrame,
    bg_disagg_test: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    test_dates = set(pd.to_datetime(test_city["ds"], errors="coerce").dropna())
    actuals = weekly_full.copy()
    actuals["ds"] = pd.to_datetime(actuals["WeekStart"], errors="coerce")
    actuals = actuals[actuals["ds"].isin(test_dates)].copy()
    actuals = actuals.rename(columns={"Barangay_key": "barangay", "Cases": "y_true"})
    actuals = actuals[["barangay", "ds", "y_true"]]

    preds = bg_disagg_test.copy()
    preds["ds"] = pd.to_datetime(preds["ds"], errors="coerce")
    preds = preds.rename(columns={"Barangay_key": "barangay"})
    preds = preds[["barangay", "ds", "yhat"]]

    merged = actuals.merge(preds, on=["barangay", "ds"], how="left")
    merged["y_true"] = pd.to_numeric(merged["y_true"], errors="coerce").fillna(0.0)
    merged["yhat"] = pd.to_numeric(merged["yhat"], errors="coerce").fillna(0.0)
    err = merged["y_true"] - merged["yhat"]

    disagg_row = pd.DataFrame(
        [
            {
                "model_name": "disagg",
                "n_barangays": int(merged["barangay"].nunique()),
                "n_rows": int(len(merged)),
                "coverage_rows": int(len(merged)),
                "RMSE": float(np.sqrt((err**2).mean())) if len(merged) else float("nan"),
                "MAE": float(err.abs().mean()) if len(merged) else float("nan"),
                "sMAPE": _smape(merged["y_true"], merged["yhat"]) if len(merged) else float("nan"),
                "run_id": cfg.run_id,
            }
        ]
    )
    disagg_row.to_csv(cfg.out / "local_model_metrics.csv", index=False)

    preferred_row = pd.DataFrame(
        [
            {
                "model_name": "preferred_selected",
                "n_barangays": int(merged["barangay"].nunique()),
                "n_rows": int(len(merged)),
                "coverage_rows": int(len(merged)),
                "RMSE": float(disagg_row.iloc[0]["RMSE"]),
                "MAE": float(disagg_row.iloc[0]["MAE"]),
                "sMAPE": float(disagg_row.iloc[0]["sMAPE"]),
                "chosen_disagg_barangays": int(merged["barangay"].nunique()),
                "chosen_local_prophet_barangays": 0,
                "chosen_local_arima_barangays": 0,
                "run_id": cfg.run_id,
            }
        ]
    )
    preferred_row.to_csv(cfg.out / "preferred_backtest_metrics.csv", index=False)
    return disagg_row, preferred_row


def run_backtest(cfg: Config = DEFAULT_CFG) -> None:
    cfg = replace(cfg, run_kind="backtest")
    cfg = _init_run(cfg)

    df, _, pending_registry_rows = load_and_clean(cfg)
    df.to_csv(cfg.out / "dengue_cleaned_pre_fp.csv", index=False, encoding="utf-8-sig")

    df = standardize_barangays(df)
    if cfg.incoming_mode == "incremental":
        df = incremental_filter(df, cfg)
    df = fingerprint_dedupe(df, cfg)

    persist_clean(df, cfg)
    finalize_ingestion_registry(cfg, pending_registry_rows)
    validation_summary(df, cfg)

    weekly_full = weekly_aggregation(df, cfg)
    city_weekly = build_city_series(weekly_full, cfg)

    train_end = pd.to_datetime(cfg.backtest_end_date)
    city_prophet, train_city, test_city, _ = train_test_split_city(city_weekly, cfg, train_end=train_end, require_test=True)

    eval_horizon = len(test_city)
    future_horizon = resolve_horizon(cfg, test_len=eval_horizon)

    PROPHET_OK, model_prophet, city_prophet_test, city_prophet_future, metrics_prophet = fit_prophet(
        train_city, test_city, cfg, future_horizon
    )
    ARIMA_OK, model_arima, city_arima_test, metrics_arima = fit_arima(train_city, test_city, cfg, eval_horizon)
    city_arima_future = _build_city_arima_future(
        model_arima=model_arima,
        train_city=train_city,
        test_city=test_city,
        horizon=future_horizon,
    )
    city_metrics_df = _save_city_metrics_table(cfg, metrics_prophet, metrics_arima)
    city_backtest_df = _save_city_backtest_predictions(
        cfg,
        test_city=test_city,
        city_prophet_test=city_prophet_test,
        city_arima_test=city_arima_test,
    )

    y_test = test_city.set_index("ds")["y"].sort_index()
    y_test.index = pd.DatetimeIndex(y_test.index)
    y_test = y_test.asfreq("W-MON")

    comparison_plot(y_test, city_arima_test, city_prophet_test, cfg)

    chosen_city_model, city_future = select_city_model(
        metrics_prophet,
        metrics_arima,
        city_prophet_test,
        city_arima_test,
        city_prophet,
        train_city.set_index("ds")["y"].sort_index().asfreq("W-MON"),
        model_prophet,
        model_arima,
        cfg,
        test_len=len(test_city),
        horizon=future_horizon,
    )

    city_test = city_prophet_test if chosen_city_model == "prophet" else city_arima_test

    city_test_out = city_test.copy()
    city_test_out["run_id"] = cfg.run_id
    city_test_out = city_test_out.rename(columns={"ds": "week_start"})
    city_test_out.to_csv(cfg.out / "city_forecasts_test.csv", index=False)

    city_future_out = city_future.copy()
    city_future_out["run_id"] = cfg.run_id
    city_future_out = city_future_out.rename(columns={"ds": "week_start"})
    city_future_out.to_csv(cfg.out / "city_forecasts_future.csv", index=False)

    city_prophet_test_out = city_prophet_test.copy()
    city_prophet_test_out["run_id"] = cfg.run_id
    city_prophet_test_out = city_prophet_test_out.rename(columns={"ds": "week_start"})
    city_arima_test_out = city_arima_test.copy()
    city_arima_test_out["run_id"] = cfg.run_id
    city_arima_test_out = city_arima_test_out.rename(columns={"ds": "week_start"})
    city_prophet_future_out = city_prophet_future.copy()
    city_prophet_future_out["run_id"] = cfg.run_id
    city_prophet_future_out = city_prophet_future_out.rename(columns={"ds": "week_start"})
    city_arima_future_out = city_arima_future.copy()
    city_arima_future_out["run_id"] = cfg.run_id
    city_arima_future_out = city_arima_future_out.rename(columns={"ds": "week_start"})

    city_long = pd.concat(
        [city_prophet_test_out, city_arima_test_out, city_prophet_future_out, city_arima_future_out],
        ignore_index=True,
    )
    city_long.to_csv(cfg.out / "city_forecasts_long.csv", index=False)

    alpha_smooth = 1.0
    bg_prophet_test_raw, bg_prophet_future_raw = hybrid_disaggregation(
        city_test=city_prophet_test,
        city_future=city_prophet_future,
        weekly_full=weekly_full,
        cfg=cfg,
        train_end=train_end,
        alpha_smooth=alpha_smooth,
    )
    bg_arima_test_raw, bg_arima_future_raw = hybrid_disaggregation(
        city_test=city_arima_test,
        city_future=city_arima_future,
        weekly_full=weekly_full,
        cfg=cfg,
        train_end=train_end,
        alpha_smooth=alpha_smooth,
    )
    bg_prophet_test = _tag_barangay_method(bg_prophet_test_raw, "prophet")
    bg_prophet_future = _tag_barangay_method(bg_prophet_future_raw, "prophet")
    bg_arima_test = _tag_barangay_method(bg_arima_test_raw, "arima")
    bg_arima_future = _tag_barangay_method(bg_arima_future_raw, "arima")
    bg_disagg_test = bg_prophet_test_raw if chosen_city_model == "prophet" else bg_arima_test_raw
    bg_disagg_future = bg_prophet_future_raw if chosen_city_model == "prophet" else bg_arima_future_raw
    bg_backtest_long = pd.concat([bg_prophet_test, bg_arima_test], ignore_index=True)
    bg_future_long = pd.concat([bg_prophet_future, bg_arima_future], ignore_index=True)

    run_metadata_df = _save_run_metadata(
        cfg,
        city_weekly=city_weekly,
        train_city=train_city,
        test_city=test_city,
        forecast_horizon_weeks=future_horizon,
        selected_primary_model=chosen_city_model,
        alpha_smooth=alpha_smooth,
    )
    barangay_backtest_df = _save_barangay_backtest_predictions(
        cfg,
        weekly_full=weekly_full,
        test_city=test_city,
        bg_backtest_long=bg_backtest_long,
    )
    coherence_backtest_df = _save_multi_method_coherence(
        cfg,
        city_long_df=pd.concat([city_prophet_test, city_arima_test], ignore_index=True),
        barangay_long_df=bg_backtest_long,
        filename="coherence_check_backtest.csv",
        horizon_type="test",
    )
    coherence_future_df = _save_multi_method_coherence(
        cfg,
        city_long_df=pd.concat([city_prophet_future, city_arima_future], ignore_index=True),
        barangay_long_df=bg_future_long,
        filename="coherence_check_future.csv",
        horizon_type="future",
    )
    barangay_metric_dist_df = _save_barangay_metric_distribution(
        cfg,
        barangay_backtest_df=barangay_backtest_df,
    )
    barangay_risk_scores_df = _save_barangay_risk_scores(
        cfg,
        weekly_full=weekly_full,
        bg_future=bg_future_long,
        epsilon=1.0,
    )

    avg_smape = prophet_additional_diagnostics(PROPHET_OK, city_prophet_test, test_city)
    plot_sample_barangays(weekly_full, bg_disagg_future, cfg)
    barangay_error_ranking(weekly_full, bg_disagg_test, test_city, cfg)

    prophet_cross_validation(PROPHET_OK, model_prophet, cfg)
    model_health_report(df, weekly_full, metrics_prophet, metrics_arima, avg_smape, diff=float("nan"))

    _require_backtest(cfg, "Step19 (reconcile)")
    all_barangays = sorted(weekly_full["Barangay_key"].unique().tolist())
    local_perf_df = _build_disagg_only_policy(cfg, all_barangays)
    local_long_df = _empty_local_forecasts(cfg)
    local_metrics_df, preferred_metrics_df = _save_disagg_only_backtest_metrics(
        cfg,
        weekly_full=weekly_full,
        test_city=test_city,
        bg_disagg_test=bg_disagg_test,
    )

    failure_summary_df = _save_model_failure_summary(
        cfg,
        run_kind="backtest",
        prophet_ok=PROPHET_OK,
        arima_ok=ARIMA_OK,
        local_summary_df=_disabled_local_failure_summary(),
    )
    arima_orders_df = _save_arima_selected_orders(
        cfg,
        city_model_arima=model_arima,
        local_orders_df=pd.DataFrame(),
        run_kind="backtest",
    )

    preferred_future_df, all_models_future_df = reconcile_forecasts(
        disagg_future=bg_disagg_future,
        local_forecasts_long=local_long_df,
        local_perf=local_perf_df,
        city_future=city_future,
        cfg=cfg,
        keep_all_models=True,
    )
    all_models_future_df = _build_barangay_all_models_future(
        cfg,
        prophet_future=bg_prophet_future,
        arima_future=bg_arima_future,
        preferred_future=preferred_future_df,
    )
    all_models_future_df.to_csv(cfg.out / "barangay_forecasts_all_models_future_long.csv", index=False)
    _ = (
        preferred_future_df,
        all_models_future_df,
        city_backtest_df,
        city_prophet_future,
        city_arima_future,
        ARIMA_OK,
        run_metadata_df,
        barangay_backtest_df,
        coherence_backtest_df,
        coherence_future_df,
        barangay_metric_dist_df,
        barangay_risk_scores_df,
        city_metrics_df,
        local_metrics_df,
        preferred_metrics_df,
        failure_summary_df,
        arima_orders_df,
    )

    try:
        upload_to_supabase(cfg)
        print("Supabase export completed.")
    except Exception as e:
        print(f"Supabase export skipped: {e}")


def run_production(cfg: Config = DEFAULT_CFG) -> None:
    cfg = replace(cfg, run_kind="production")
    cfg = _init_run(cfg)

    df, _, pending_registry_rows = load_and_clean(cfg)
    df = standardize_barangays(df)
    if cfg.incoming_mode == "incremental":
        df = incremental_filter(df, cfg)
    df = fingerprint_dedupe(df, cfg)
    persist_clean(df, cfg)
    finalize_ingestion_registry(cfg, pending_registry_rows)

    weekly_full = weekly_aggregation(df, cfg)
    city_weekly = build_city_series(weekly_full, cfg)

    city_prophet, train_city, test_city, _ = train_test_split_city(
        city_weekly,
        cfg,
        train_end=None,
        require_test=False,
    )

    prod_train_end = pd.to_datetime(train_city["ds"], errors="raise").max()
    horizon = int(getattr(cfg, "production_horizon_weeks", 12))

    PROPHET_OK, model_prophet, city_prophet_test, city_prophet_future, metrics_prophet = fit_prophet(
        train_city, test_city, cfg, horizon
    )
    ARIMA_OK, model_arima, city_arima_test, metrics_arima = fit_arima(train_city, test_city, cfg, horizon)
    city_arima_future = _build_city_arima_future(
        model_arima=model_arima,
        train_city=train_city,
        test_city=test_city,
        horizon=horizon,
    )

    chosen_city_model, city_future = select_city_model(
        metrics_prophet,
        metrics_arima,
        city_prophet_test,
        city_arima_test,
        city_prophet,
        train_city.set_index("ds")["y"].sort_index().asfreq("W-MON"),
        model_prophet,
        model_arima,
        cfg,
        test_len=0,
        horizon=horizon,
    )

    _ = (chosen_city_model, city_prophet_future, ARIMA_OK)

    city_future_out = city_future.copy()
    city_future_out["run_id"] = cfg.run_id
    city_future_out = city_future_out.rename(columns={"ds": "week_start"})
    city_future_out.to_csv(cfg.out / "city_forecasts_future.csv", index=False)
    city_prophet_future_out = city_prophet_future.copy()
    city_prophet_future_out["run_id"] = cfg.run_id
    city_prophet_future_out = city_prophet_future_out.rename(columns={"ds": "week_start"})
    city_arima_future_out = city_arima_future.copy()
    city_arima_future_out["run_id"] = cfg.run_id
    city_arima_future_out = city_arima_future_out.rename(columns={"ds": "week_start"})
    city_long = pd.concat([city_prophet_future_out, city_arima_future_out], ignore_index=True)
    city_long.to_csv(cfg.out / "city_forecasts_long.csv", index=False)

    empty_city_test = pd.DataFrame(columns=city_future.columns)
    alpha_smooth = 1.0
    bg_prophet_test_raw, bg_prophet_future_raw = hybrid_disaggregation(
        city_test=empty_city_test,
        city_future=city_prophet_future,
        weekly_full=weekly_full,
        cfg=cfg,
        train_end=prod_train_end,
        alpha_smooth=alpha_smooth,
    )
    bg_arima_test_raw, bg_arima_future_raw = hybrid_disaggregation(
        city_test=empty_city_test,
        city_future=city_arima_future,
        weekly_full=weekly_full,
        cfg=cfg,
        train_end=prod_train_end,
        alpha_smooth=alpha_smooth,
    )
    _ = (bg_prophet_test_raw, bg_arima_test_raw)
    bg_prophet_future = _tag_barangay_method(bg_prophet_future_raw, "prophet")
    bg_arima_future = _tag_barangay_method(bg_arima_future_raw, "arima")
    bg_disagg_future = bg_prophet_future_raw if chosen_city_model == "prophet" else bg_arima_future_raw

    run_metadata_df = _save_run_metadata(
        cfg,
        city_weekly=city_weekly,
        train_city=train_city,
        test_city=test_city,
        forecast_horizon_weeks=horizon,
        selected_primary_model=chosen_city_model,
        alpha_smooth=alpha_smooth,
    )
    coherence_future_df = _save_multi_method_coherence(
        cfg,
        city_long_df=pd.concat([city_prophet_future, city_arima_future], ignore_index=True),
        barangay_long_df=pd.concat([bg_prophet_future, bg_arima_future], ignore_index=True),
        filename="coherence_check_future.csv",
        horizon_type="future",
    )
    barangay_risk_scores_df = _save_barangay_risk_scores(
        cfg,
        weekly_full=weekly_full,
        bg_future=pd.concat([bg_prophet_future, bg_arima_future], ignore_index=True),
        epsilon=1.0,
    )

    all_barangays = sorted(weekly_full["Barangay_key"].unique().tolist())

    policy = _build_disagg_only_policy(cfg, all_barangays)

    if "Barangay_key" not in policy.columns or "Chosen" not in policy.columns:
        raise RuntimeError("Policy file must contain columns: Barangay_key, Chosen")

    policy_keys = set(policy["Barangay_key"].astype(str))
    prod_keys = set(map(str, all_barangays))

    print(f"Policy coverage: {len(prod_keys & policy_keys)}/{len(prod_keys)}")
    missing_in_policy = sorted(prod_keys - policy_keys)[:10]
    extra_in_policy = sorted(policy_keys - prod_keys)[:10]
    if missing_in_policy:
        print("Missing in policy (sample):", missing_in_policy)
    if extra_in_policy:
        print("Extra in policy (sample):", extra_in_policy)

    local_long_future = _empty_local_forecasts(cfg)
    production_local_failure_summary = _disabled_local_failure_summary()
    local_arima_orders_df = pd.DataFrame()

    failure_summary_df = _save_model_failure_summary(
        cfg,
        run_kind="production",
        prophet_ok=PROPHET_OK,
        arima_ok=ARIMA_OK,
        local_summary_df=production_local_failure_summary,
    )
    _ = failure_summary_df
    arima_orders_df = _save_arima_selected_orders(
        cfg,
        city_model_arima=model_arima,
        local_orders_df=local_arima_orders_df,
        run_kind="production",
    )
    _ = arima_orders_df

    preferred_future_df, all_models_future_df = reconcile_forecasts(
        disagg_future=bg_disagg_future,
        local_forecasts_long=local_long_future,
        local_perf=policy,
        city_future=city_future,
        cfg=cfg,
        keep_all_models=True,
    )
    _ = preferred_future_df

    all_models_future_df = _build_barangay_all_models_future(
        cfg,
        prophet_future=bg_prophet_future,
        arima_future=bg_arima_future,
        preferred_future=preferred_future_df,
    )
    all_models_future_df.to_csv(cfg.out / "barangay_forecasts_long.csv", index=False)
    _ = (run_metadata_df, coherence_future_df, barangay_risk_scores_df)

    vc = all_models_future_df["model_name"].value_counts(dropna=False)
    print("model_name counts:\n", vc)

    expected = len(all_barangays) * horizon
    for m in ["prophet", "arima", "preferred"]:
        if vc.get(m, 0) != expected:
            print(f"Unexpected count for {m}: got {vc.get(m, 0)} expected {expected}")

    try:
        upload_to_supabase(cfg)
        print("Supabase export completed.")
    except Exception as e:
        print(f"Supabase export skipped: {e}")

def run_pipeline(cfg: Config = DEFAULT_CFG) -> None:
    if getattr(cfg, "run_kind", "backtest") == "production":
        return run_production(cfg)
    return run_backtest(cfg)


if __name__ == "__main__":
    run_pipeline(DEFAULT_CFG)
