# ============================================================
# file: denguard/run_pipeline.py
# (PATCHED) fix wiring for standardized forecasts
# ============================================================
from __future__ import annotations

import pandas as pd
from denguard.config import DEFAULT_CFG, Config
from denguard.utils import ensure_outdir

from denguard.steps.step1_load_clean import load_and_clean, persist_clean
from denguard.steps.step2_standardize import standardize_barangays
from denguard.steps.step24_incremental_filter import incremental_filter
from denguard.steps.step25_fingerprint_dedupe import fingerprint_dedupe
from denguard.steps.step3_validation import validation_summary
from denguard.steps.step4_weekly_agg import weekly_aggregation
from denguard.steps.step5_city_series import build_city_series
from denguard.steps.step6_split import train_test_split_city
from denguard.steps.step7_prophet import fit_prophet
from denguard.steps.step8_arima import fit_arima
from denguard.steps.step9_comparison import comparison_plot
from denguard.selection import select_city_model
from denguard.steps.step10_disagg import hybrid_disaggregation
from denguard.steps.step11_prophet_diag import prophet_additional_diagnostics
from denguard.steps.step12_plot_sample import plot_sample_barangays
from denguard.steps.step13_errors import barangay_error_ranking
from denguard.steps.step15_prophet_cv import prophet_cross_validation
from denguard.steps.step16_health import model_health_report
# from denguard.steps.step17_tiers import tier_classification
from denguard.steps.step18_local_models import local_models_tierA
from denguard.steps.step19_reconcile import reconcile_forecasts
from denguard.export_supabase import upload_to_supabase
from denguard.horizon import resolve_horizon
from denguard.steps.step17_tiers import local_eligibility

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

def _init_run(cfg: Config) -> Config:
    ensure_outdir(cfg.out)
    run_id = cfg.run_id or str(uuid4())
    started_at = cfg.run_started_at_utc or datetime.now(timezone.utc).isoformat()
    cfg = replace(cfg, run_id=run_id, run_started_at_utc=started_at)

    run_row = pd.DataFrame([{
        "run_id": run_id,
        "run_started_at_utc": started_at,
        "run_kind": getattr(cfg, "run_kind", "backtest"),
        "backtest_end_date": getattr(cfg, "backtest_end_date", None),
        "incoming_mode": cfg.incoming_mode,
        "forecast_weeks_override": cfg.forecast_weeks_override,
    }])
    run_row.to_csv(cfg.out / "runs.csv", mode="a", header=not (cfg.out / "runs.csv").exists(), index=False)
    print(f"🏷️ run_id = {run_id} | run_kind = {getattr(cfg,'run_kind','backtest')}")
    return cfg

def _require_backtest(cfg: Config, step_name: str) -> None:
    if getattr(cfg, "run_kind", "backtest") != "backtest":
        raise RuntimeError(
            f"{step_name} is backtest-only (needs a non-empty test window + disagg_test baseline). "
            f"Current run_kind={getattr(cfg,'run_kind',None)}."
        )


def run_backtest(cfg: Config = DEFAULT_CFG) -> None:
    cfg = replace(cfg, run_kind="backtest")
    cfg = _init_run(cfg)

    df, _ = load_and_clean(cfg)
    df.to_csv(cfg.out / "dengue_cleaned_pre_fp.csv", index=False, encoding="utf-8-sig")

    df = standardize_barangays(df)
    if cfg.incoming_mode == "incremental":
        df = incremental_filter(df, cfg)
    df = fingerprint_dedupe(df, cfg)

    persist_clean(df, cfg)
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
    ARIMA_OK, model_arima, city_arima_test, metrics_arima = fit_arima(
        train_city, test_city, cfg, eval_horizon
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

    # write city forecasts (test + future)
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

    # disaggregation (train_end = backtest cutoff)
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

    _require_backtest(cfg, "Step17/18/19 (tiers/local/reconcile)")

    elig_df, eligible_keys = local_eligibility(weekly_full, cfg, train_end=train_end)

    all_barangays = sorted(weekly_full["Barangay_key"].unique().tolist())

    local_perf_df, local_long_df = local_models_tierA(
        barangay_keys=all_barangays,
        eligible_keys=eligible_keys,
        weekly_full=weekly_full,
        test_city=test_city,
        train_end=train_end,
        horizon=future_horizon,
        PROPHET_OK=PROPHET_OK,
        cfg=cfg,
        disagg_test_df=bg_disagg_test,
    )


    preferred_future_df, all_models_future_df = reconcile_forecasts(
        disagg_future=bg_disagg_future,
        local_forecasts_long=local_long_df,
        local_perf=local_perf_df,
        city_future=city_future,
        cfg=cfg,
        keep_all_models=True,
    )

    try:
        upload_to_supabase(cfg)
        print("✅ Supabase export completed.")
    except Exception as e:
        print(f"ℹ️ Supabase export skipped: {e}")


def run_production(cfg: Config = DEFAULT_CFG) -> None:
    cfg = replace(cfg, run_kind="production")
    cfg = _init_run(cfg)

    df, _ = load_and_clean(cfg)
    df = standardize_barangays(df)
    if cfg.incoming_mode == "incremental":
        df = incremental_filter(df, cfg)
    df = fingerprint_dedupe(df, cfg)
    persist_clean(df, cfg)

    weekly_full = weekly_aggregation(df, cfg)
    city_weekly = build_city_series(weekly_full, cfg)

    # Production: train on latest observed (Step6 uses latest observed when run_kind != backtest)
    city_prophet, train_city, test_city, _ = train_test_split_city(
        city_weekly,
        cfg,
        train_end=None,
        require_test=False,
    )

    prod_train_end = pd.to_datetime(train_city["ds"], errors="raise").max()


    horizon = int(getattr(cfg, "production_horizon_weeks", 12))

    # Fit both models (test_city empty allowed)
    PROPHET_OK, model_prophet, city_prophet_test, city_prophet_future, metrics_prophet = fit_prophet(
        train_city, test_city, cfg, horizon
    )
    ARIMA_OK, model_arima, city_arima_test, metrics_arima = fit_arima(
        train_city, test_city, cfg, horizon
    )

    # Choose model by cfg.production_city_model (because test_len==0)
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

    # Write ONLY future (dashboard uses this)
    city_future_out = city_future.copy()
    city_future_out["run_id"] = cfg.run_id
    city_future_out = city_future_out.rename(columns={"ds": "week_start"})
    city_future_out.to_csv(cfg.out / "city_forecasts_future.csv", index=False)

    # Also write a "long" file with only future for production
    city_future_out.to_csv(cfg.out / "city_forecasts_long.csv", index=False)

    # Disaggregation uses production train_end (latest observed)
    empty_city_test = pd.DataFrame(columns=city_future.columns)  # keep signature happy
    bg_disagg_test, bg_disagg_future = hybrid_disaggregation(
        city_test=empty_city_test,
        city_future=city_future,
        weekly_full=weekly_full,
        cfg=cfg,
        train_end=prod_train_end,
    )

    # Production minimal: export disagg as preferred (thesis-safe, doesn’t invent evaluation)
    preferred_future = bg_disagg_future.copy()
    preferred_future["model_name"] = "preferred"

    preferred_out = preferred_future.rename(columns={"Barangay_key": "name", "ds": "week_start"}).copy()
    preferred_out["run_id"] = cfg.run_id
    preferred_out.to_csv(cfg.out / "barangay_forecasts_preferred_future_long.csv", index=False)

    # Export multi-model grid optional: here we export only preferred+disagg if you want later.
    all_models_out = pd.concat([preferred_future, bg_disagg_future], ignore_index=True)
    all_models_out = all_models_out.rename(columns={"Barangay_key": "name", "ds": "week_start"}).copy()
    all_models_out["run_id"] = cfg.run_id
    all_models_out["status"] = "ok"
    all_models_out.to_csv(cfg.out / "barangay_forecasts_all_models_future_long.csv", index=False)

    try:
        upload_to_supabase(cfg)
        print("✅ Supabase export completed.")
    except Exception as e:
        print(f"ℹ️ Supabase export skipped: {e}")

def run_pipeline(cfg: Config = DEFAULT_CFG) -> None:
    # Backwards compatible entry point
    if getattr(cfg, "run_kind", "backtest") == "production":
        return run_production(cfg)
    return run_backtest(cfg)


if __name__ == "__main__":
    run_pipeline(DEFAULT_CFG)