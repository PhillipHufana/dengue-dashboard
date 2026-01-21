from __future__ import annotations
from denguard.horizon import resolve_horizon

import numpy as np
import pandas as pd

from denguard.config import DEFAULT_CFG
from denguard.utils import ensure_outdir

from denguard.steps.step1_load_clean import load_and_clean
from denguard.steps.step2_standardize import standardize_barangays
from denguard.steps.step4_weekly_agg import weekly_aggregation
from denguard.steps.step5_city_series import build_city_series
from denguard.steps.step6_split import train_test_split_city

from denguard.steps.step7_prophet import fit_prophet
from denguard.steps.step8_arima import fit_arima
from denguard.selection import select_city_model
from denguard.steps.step10_disagg import hybrid_disaggregation


def _assert_weekly_wmon(ds: pd.Series, name: str) -> None:
    ds = pd.to_datetime(ds, errors="raise").sort_values().reset_index(drop=True)
    assert ds.dt.dayofweek.nunique() == 1 and int(ds.dt.dayofweek.iloc[0]) == 0, f"{name}: not W-MON"
    diffs = ds.diff().dropna()
    assert (diffs == pd.Timedelta(days=7)).all(), f"{name}: not continuous weekly steps"


def run(cfg=DEFAULT_CFG) -> None:
    ensure_outdir(cfg.out)

    # ---- Build inputs up to Step 6 ----
    df, _ = load_and_clean(cfg)
    df = standardize_barangays(df)

    weekly_full = weekly_aggregation(df, cfg)
    city_weekly = build_city_series(weekly_full, cfg)
    city_prophet, train_city, test_city, _ = train_test_split_city(city_weekly, cfg)

    eval_horizon = int(len(test_city))                # ALWAYS full test window
    future_horizon = resolve_horizon(cfg, test_len=eval_horizon)  # override applies here

    assert eval_horizon > 0 and future_horizon > 0

    # ---- Invariants on ds ----
    _assert_weekly_wmon(train_city["ds"], "train_city.ds")
    _assert_weekly_wmon(test_city["ds"], "test_city.ds")
    _assert_weekly_wmon(city_prophet["ds"], "city_prophet.ds")



    # ---- Step 7/8 ----
    ok_p, model_p, forecast_p, met_p = fit_prophet(train_city, test_city, cfg, horizon=eval_horizon)
    ok_a, model_a, pred_a, met_a = fit_arima(train_city, test_city, cfg, horizon=eval_horizon)


    # Prophet forecast must cover test dates (at least)
    if ok_p:
        assert forecast_p is not None
        assert {"ds","yhat","yhat_lower","yhat_upper"}.issubset(forecast_p.columns)
        # ensure predictions exist for test period
        joined = test_city.merge(forecast_p[["ds","yhat"]], on="ds", how="left")
        assert joined["yhat"].notna().any(), "Prophet: no yhat on test ds"
        assert (forecast_p["yhat_lower"] <= forecast_p["yhat_upper"]).all(), "Prophet: bad intervals"

    # ARIMA pred_df must be aligned to test (index=ds)
    if ok_a:
        assert pred_a is not None
        assert isinstance(pred_a.index, pd.DatetimeIndex)
        assert {"yhat","yhat_lower","yhat_upper"}.issubset(pred_a.columns)
        assert pred_a["yhat"].notna().all(), "ARIMA: NaN yhat"
        assert (pred_a["yhat_lower"] <= pred_a["yhat_upper"]).all(), "ARIMA: bad intervals"
        assert len(pred_a) == len(test_city), f"ARIMA pred_a len {len(pred_a)} != test len {len(test_city)}"
        test_index = pd.DatetimeIndex(pd.to_datetime(test_city["ds"]).sort_values())
        assert pred_a.index.equals(test_index), "ARIMA pred_a index does not match test_city ds exactly"


    # ---- Selection (Step 9 logic is plotting only; selection must return FUTURE only) ----
    # Build y_train (not used by selector but you pass it)
    y_train = train_city.set_index("ds")["y"].sort_index().asfreq("W-MON")

    chosen_model, chosen_future = select_city_model(
        met_p, met_a,
        forecast_p,
        pred_a,
        city_prophet,
        y_train,
        model_p, model_a,
        cfg,
        horizon=future_horizon,
    )

    assert len(chosen_future) == future_horizon, \
        f"chosen_future wrong length: {len(chosen_future)} != {future_horizon}"


    assert chosen_model in ("Prophet","ARIMA")
    assert isinstance(chosen_future, pd.DataFrame)
    assert {"ds","yhat","yhat_lower","yhat_upper"}.issubset(chosen_future.columns)
    _assert_weekly_wmon(chosen_future["ds"], "chosen_future.ds")

    # Future-only: all ds must be strictly after last observed city week
    last_obs = pd.to_datetime(city_prophet["ds"]).max()
    assert (pd.to_datetime(chosen_future["ds"]) > last_obs).all(), "chosen_future includes non-future dates"

    # ---- Step 10: disaggregation ----
    barangay_fc, diff, out_city = hybrid_disaggregation(
        chosen_model,
        chosen_future,
        forecast_p,
        pred_a,
        test_city,
        weekly_full,
        cfg,
    )

    # Shape checks
    n_keys = int(pd.read_csv(cfg.canon_csv)["canonical_name"].shape[0])
    expected_rows = (len(test_city) + future_horizon) * n_keys
    assert barangay_fc.shape[0] == expected_rows, f"barangay_fc rows {barangay_fc.shape[0]} != {expected_rows}"

    # Uniqueness: one row per (Barangay_key, ds)
    assert barangay_fc.duplicated(["Barangay_key","ds"]).sum() == 0, "duplicates in barangay_fc"

    # Sum-to-city check (should be ~0)
    check = (
        barangay_fc.groupby("ds")["Forecast"].sum()
        .reset_index()
        .merge(out_city[["ds","CityForecast"]], on="ds", how="left")
    )
    mae_sum = float((check["Forecast"] - check["CityForecast"]).abs().mean())
    assert mae_sum < 1e-6, f"disagg sum mismatch too large: {mae_sum}"
    print("✅ PASS: steps 7–10 + selection are consistent.")


if __name__ == "__main__":
    run()
