# file: denguard/run_pipeline.py  (or wherever your run_pipeline currently lives)
from __future__ import annotations

import pandas as pd
from denguard.config import DEFAULT_CFG, Config
from denguard.utils import ensure_outdir

# Step modules
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
from denguard.steps.step17_tiers import tier_classification
from denguard.steps.step18_local_models import local_models_tierA
from denguard.steps.step19_reconcile import reconcile_forecasts
from denguard.export_supabase import upload_to_supabase


# NEW: horizon resolver
from denguard.horizon import resolve_horizon




def run_pipeline(cfg: Config = DEFAULT_CFG) -> None:
    ensure_outdir(cfg.out)

    # Step 1–3
    # Step 1–3
    df, _ = load_and_clean(cfg)

    df.to_csv(cfg.out / "dengue_cleaned_pre_fp.csv", index=False, encoding="utf-8-sig")

    df = standardize_barangays(df)

    if cfg.incoming_mode == "incremental":
        df = incremental_filter(df, cfg)

    df = fingerprint_dedupe(df, cfg)

    persist_clean(df, cfg)
    validation_summary(df, cfg)

    # Step 4–6
    weekly_full = weekly_aggregation(df, cfg)
    city_weekly = build_city_series(weekly_full, cfg)
    city_prophet, train_city, test_city, _ = train_test_split_city(city_weekly, cfg)

    # Horizons
    eval_horizon = len(test_city)
    future_horizon = resolve_horizon(cfg, test_len=eval_horizon)

    # Step 7–8 (EVALUATION forecasts: full test length)
    PROPHET_OK, model_prophet, forecast_prophet, metrics_prophet = fit_prophet(
        train_city, test_city, cfg, eval_horizon
    )

    ARIMA_OK, model_arima, forecast_arima, metrics_arima = fit_arima(
        train_city, test_city, cfg, eval_horizon
    )

    # Build y_train / y_test for plotting (weekly W-MON)
    y_train = train_city.set_index("ds")["y"].sort_index()
    y_train.index = pd.DatetimeIndex(y_train.index)
    y_train = y_train.asfreq("W-MON")

    y_test = test_city.set_index("ds")["y"].sort_index()
    y_test.index = pd.DatetimeIndex(y_test.index)
    y_test = y_test.asfreq("W-MON")

    # Step 9
    comparison_plot(y_test, forecast_arima, forecast_prophet, cfg)

    # Select best city model + build FUTURE forecast (deployment horizon)
    chosen_city_model, chosen_city_forecast = select_city_model(
        metrics_prophet,
        metrics_arima,
        forecast_prophet,
        forecast_arima,
        city_prophet,
        y_train,
        model_prophet,
        model_arima,
        cfg,
        future_horizon,
    )

    # Step 10
    barangay_forecasts, diff, chosen = hybrid_disaggregation(
        chosen_city_model,
        chosen_city_forecast,
        forecast_prophet,
        forecast_arima,
        test_city,
        weekly_full,
        cfg,
    )

    # Step 11
    avg_smape = prophet_additional_diagnostics(
        PROPHET_OK, forecast_prophet, test_city
    )


    # Step 12
    plot_sample_barangays(weekly_full, barangay_forecasts, cfg)

    # Step 13
    barangay_error_ranking(
        weekly_full, barangay_forecasts, test_city, cfg
    )

    # Step 15
    prophet_cross_validation(PROPHET_OK, model_prophet, cfg)

    # Step 16
    model_health_report(
        df,
        weekly_full,
        metrics_prophet,
        metrics_arima,
        avg_smape,
        diff,
    )

    # Step 17 — Tiers
    tiers_df, tierA, _, _ = tier_classification(weekly_full, cfg)

    # Step 18 — Local models
    train_end = pd.to_datetime(cfg.train_end_date)
    local_results_df, local_forecasts_all_df = local_models_tierA(
        tierA,
        weekly_full,
        test_city,
        train_end,
        future_horizon,      # use the resolved horizon here too
        PROPHET_OK,
        cfg,
    )

    # Step 19 — Final reconciliation
    final_forecast = reconcile_forecasts(
        barangay_forecasts,
        local_forecasts_all_df,
        chosen_city_forecast,
        cfg,
    )

    # ============================================
    # Step 20 — Export to Supabase (single source)
    # ============================================
    try:
        upload_to_supabase(cfg)
        print("✅ Supabase export completed.")
    except Exception as e:
        print(f"ℹ️ Supabase export skipped: {e}")


if __name__ == "__main__":
    run_pipeline(DEFAULT_CFG)
