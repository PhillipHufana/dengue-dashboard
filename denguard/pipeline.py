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
from denguard.steps.step18_local_models import save_local_metrics_tables
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
    city_metrics_df = _save_city_metrics_table(cfg, metrics_prophet, metrics_arima)

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

    city_long = pd.concat([city_test_out, city_future_out], ignore_index=True)
    city_long.to_csv(cfg.out / "city_forecasts_long.csv", index=False)

    bg_disagg_test, bg_disagg_future = hybrid_disaggregation(
        city_test=city_test,
        city_future=city_future,
        weekly_full=weekly_full,
        cfg=cfg,
        train_end=train_end,
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
    raw_local_metrics_df, preferred_metrics_df = save_local_metrics_tables(
        weekly_full=weekly_full,
        test_city=test_city,
        disagg_test_df=bg_disagg_test,
        local_forecasts_long=local_long_df,
        local_perf=local_perf_df,
        cfg=cfg,
    )
    local_metrics_df = raw_local_metrics_df[raw_local_metrics_df["model_name"] == "disagg"].copy()
    local_metrics_df.to_csv(cfg.out / "local_model_metrics.csv", index=False)

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
    _ = (
        preferred_future_df,
        all_models_future_df,
        city_prophet_future,
        ARIMA_OK,
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
        print(f"â„¹ï¸ Supabase export skipped: {e}")


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
    city_future_out.to_csv(cfg.out / "city_forecasts_long.csv", index=False)

    empty_city_test = pd.DataFrame(columns=city_future.columns)
    bg_disagg_test, bg_disagg_future = hybrid_disaggregation(
        city_test=empty_city_test,
        city_future=city_future,
        weekly_full=weekly_full,
        cfg=cfg,
        train_end=prod_train_end,
    )
    _ = bg_disagg_test

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
        print("âš ï¸ Missing in policy (sample):", missing_in_policy)
    if extra_in_policy:
        print("âš ï¸ Extra in policy (sample):", extra_in_policy)

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

    all_models_future_df.to_csv(cfg.out / "barangay_forecasts_long.csv", index=False)

    vc = all_models_future_df["model_name"].value_counts(dropna=False)
    print("model_name counts:\n", vc)

    expected = len(all_barangays) * horizon
    for m in ["disagg", "preferred"]:
        if vc.get(m, 0) != expected:
            print(f"âš ï¸ Unexpected count for {m}: got {vc.get(m, 0)} expected {expected}")

    try:
        upload_to_supabase(cfg)
        print(" Supabase export completed.")
    except Exception as e:
        print(f"â„¹ï¸ Supabase export skipped: {e}")

def run_pipeline(cfg: Config = DEFAULT_CFG) -> None:
    if getattr(cfg, "run_kind", "backtest") == "production":
        return run_production(cfg)
    return run_backtest(cfg)


if __name__ == "__main__":
    run_pipeline(DEFAULT_CFG)
