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
from denguard.steps.step17_tiers import tier_classification
from denguard.steps.step18_local_models import local_models_tierA
from denguard.steps.step19_reconcile import reconcile_forecasts
from denguard.export_supabase import upload_to_supabase
from denguard.horizon import resolve_horizon


def run_pipeline(cfg: Config = DEFAULT_CFG) -> None:
    ensure_outdir(cfg.out)

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
    city_prophet, train_city, test_city, _ = train_test_split_city(city_weekly, cfg)

    eval_horizon = len(test_city)
    future_horizon = resolve_horizon(cfg, test_len=eval_horizon)

    # City models (test + future for Prophet; test for ARIMA; future via selection)
    PROPHET_OK, model_prophet, city_prophet_test, city_prophet_future, metrics_prophet = fit_prophet(
        train_city, test_city, cfg, eval_horizon
    )
    ARIMA_OK, model_arima, city_arima_test, metrics_arima = fit_arima(
        train_city, test_city, cfg, eval_horizon
    )

    # Build y_test for plotting diagnostics
    y_test = test_city.set_index("ds")["y"].sort_index()
    y_test.index = pd.DatetimeIndex(y_test.index)
    y_test = y_test.asfreq("W-MON")

    # Step 9
    comparison_plot(y_test, city_arima_test, city_prophet_test, cfg)

    # Select best future city model
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
        future_horizon,
    )

    city_test = city_prophet_test if chosen_city_model == "prophet" else city_arima_test

    # Step 10 disagg
    bg_disagg_test, bg_disagg_future = hybrid_disaggregation(
        city_test=city_test,
        city_future=city_future,
        weekly_full=weekly_full,
        cfg=cfg,
    )

    # Step 11: needs updating if it still expects old Prophet df; pass standardized test
    avg_smape = prophet_additional_diagnostics(PROPHET_OK, city_prophet_test, test_city)

    # Step 12/13: you must decide what to plot/rank now.
    # Here we use preferred_future later; for now pass disagg_future (or all_models_future_df).
    plot_sample_barangays(weekly_full, bg_disagg_future, cfg)
    barangay_error_ranking(weekly_full, bg_disagg_test, test_city, cfg)

    prophet_cross_validation(PROPHET_OK, model_prophet, cfg)

    # diff removed; if your health report expects it, compute diff from disagg coherence if needed.
    model_health_report(df, weekly_full, metrics_prophet, metrics_arima, avg_smape, diff=float("nan"))

    tiers_df, tierA, _, _ = tier_classification(weekly_full, cfg)

    train_end = pd.to_datetime(cfg.train_end_date)
    local_perf_df, local_long_df = local_models_tierA(
        tierA, weekly_full, test_city, train_end, future_horizon, PROPHET_OK, cfg
    )

    preferred_future_df, all_models_future_df = reconcile_forecasts(
        disagg_future=bg_disagg_future,
        local_forecasts_long=local_long_df,
        local_perf=local_perf_df,
        city_future=city_future,
        cfg=cfg,
        keep_all_models=True,
    )
    def _validate_step19(preferred_future: pd.DataFrame, all_models_future: pd.DataFrame, city_future: pd.DataFrame) -> None:
        # A) schema
        required_pref = {"Barangay_key","ds","yhat","yhat_lower","yhat_upper","model_name","horizon_type"}
        assert required_pref.issubset(preferred_future.columns), f"preferred missing: {required_pref - set(preferred_future.columns)}"

        required_all = required_pref | {"status"}
        assert required_all.issubset(all_models_future.columns), f"all_models missing: {required_all - set(all_models_future.columns)}"

        # B) Monday + horizon length
        assert (pd.to_datetime(preferred_future["ds"]).dt.dayofweek == 0).all()
        assert (pd.to_datetime(all_models_future["ds"]).dt.dayofweek == 0).all()
        assert preferred_future["ds"].nunique() == city_future["ds"].nunique()

        # C) Coherence
        chk = (
            preferred_future.groupby("ds")["yhat"].sum().reset_index(name="sum_bg")
            .merge(city_future[["ds","yhat"]].rename(columns={"yhat":"city"}), on="ds")
        )
        mean_abs = (chk["sum_bg"] - chk["city"]).abs().mean()
        max_abs = (chk["sum_bg"] - chk["city"]).abs().max()
        print("STEP19 coherence mean abs diff:", float(mean_abs))
        print("STEP19 coherence max abs diff:", float(max_abs))

        # D) Grid completeness
        n_bgy = all_models_future["Barangay_key"].nunique()
        n_weeks = all_models_future["ds"].nunique()
        assert set(all_models_future["model_name"].unique()) == {"disagg","local_prophet","local_arima","preferred"}
        assert len(all_models_future) == n_bgy * n_weeks * 4
        assert all_models_future.columns.is_unique

        print("models:", sorted(all_models_future["model_name"].unique()))
        print("rows:", len(all_models_future))
        print("unique barangays:", all_models_future["Barangay_key"].nunique())
        print("unique weeks:", all_models_future["ds"].nunique())
        print("filled rate:", (all_models_future["status"]=="filled").mean())
        print("all_models columns:", all_models_future_df.columns.tolist())

        print("status in all_models?", "status" in all_models_future_df.columns)
        print(all_models_future_df[["model_name","status"]].head())

        # must hold:
        assert set(all_models_future_df["model_name"].unique()) == {"disagg","local_prophet","local_arima","preferred"}
        assert "status" in all_models_future_df.columns





        # E) filled rate
        filled_rate = (all_models_future["status"] == "filled").mean()
        print("STEP19 filled_rate:", float(filled_rate))


    _validate_step19(preferred_future_df, all_models_future_df, city_future)


    try:
        upload_to_supabase(cfg)
        print("✅ Supabase export completed.")
    except Exception as e:
        print(f"ℹ️ Supabase export skipped: {e}")


if __name__ == "__main__":
    run_pipeline(DEFAULT_CFG)