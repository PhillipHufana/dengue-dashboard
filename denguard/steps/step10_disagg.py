# denguard/steps/step10_disagg.py
from __future__ import annotations
from typing import Tuple
import numpy as np
import pandas as pd
from denguard.config import Config
from denguard.keys import make_barangay_db_key
from denguard.forecast_schema import ensure_barangay_forecast_df


def hybrid_disaggregation(
    city_test: pd.DataFrame,
    city_future: pd.DataFrame,
    weekly_full: pd.DataFrame,
    cfg: Config,
    *,
    train_end: pd.Timestamp,
    alpha_smooth: float = 1.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Top-down disaggregation using a rolling train-window proportion baseline.
    train_end is passed in:
      - backtest: cfg.backtest_end_date
      - production: last observed week in data
    """
    print("\n== STEP 10: Hybrid top-down disaggregation (standardized) ==")

    train_end = pd.to_datetime(train_end)
    window_weeks = int(getattr(cfg, "disagg_weight_weeks", 52))
    if window_weeks <= 0:
        raise ValueError(f"disagg_weight_weeks must be positive, got {window_weeks}")

    recent_start = train_end - pd.Timedelta(weeks=window_weeks - 1)

    recent = weekly_full[(weekly_full["WeekStart"] >= recent_start) & (weekly_full["WeekStart"] <= train_end)].copy()
    if recent.empty:
        recent = weekly_full[weekly_full["WeekStart"] <= train_end].copy()

    canonical = pd.read_csv(cfg.canon_csv)
    all_keys = canonical["canonical_name"].map(make_barangay_db_key).dropna().unique()

    weights = (
        recent.groupby("Barangay_key")["Cases"].sum()
        .reindex(all_keys, fill_value=0)
        .rename_axis("Barangay_key")
        .reset_index(name="Cases")
    )

    weights["Cases_smoothed"] = weights["Cases"].astype(float) + float(alpha_smooth)
    total = float(weights["Cases_smoothed"].sum())
    if total <= 0:
        raise ValueError("Cannot compute weights: total smoothed cases <= 0")

    weights["p"] = weights["Cases_smoothed"] / total
    weights = weights[["Barangay_key", "p"]]

    def _disagg(city_df: pd.DataFrame, horizon_type: str) -> pd.DataFrame:
        parts = []
        for _, r in weights.iterrows():
            b = r["Barangay_key"]
            p = float(r["p"])
            tmp = city_df.copy()
            tmp["Barangay_key"] = b
            tmp["yhat"] = tmp["yhat"] * p
            tmp["yhat_lower"] = tmp["yhat_lower"] * p
            tmp["yhat_upper"] = tmp["yhat_upper"] * p
            parts.append(tmp[["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper"]])
        out = pd.concat(parts, ignore_index=True)
        return ensure_barangay_forecast_df(out, model_name="disagg", horizon_type=horizon_type)

    bg_test = _disagg(city_test, "test") if (city_test is not None and not city_test.empty) else pd.DataFrame(
        columns=["Barangay_key","ds","yhat","yhat_lower","yhat_upper","model_name","horizon_type"]
    )
    bg_future = _disagg(city_future, "future")

    # coherence checks only if bg_test exists
    if not bg_test.empty:
        s = bg_test.groupby("ds")["yhat"].sum().reset_index()
        chk = s.merge(city_test[["ds", "yhat"]], on="ds", how="left", suffixes=("_sum", "_city"))
        diff = float((chk["yhat_sum"] - chk["yhat_city"]).abs().mean())
        print(f"✅ Disagg coherence (test) mean abs diff: {diff:.6f}")

    s = bg_future.groupby("ds")["yhat"].sum().reset_index()
    chk = s.merge(city_future[["ds", "yhat"]], on="ds", how="left", suffixes=("_sum", "_city"))
    diff = float((chk["yhat_sum"] - chk["yhat_city"]).abs().mean())
    print(f"✅ Disagg coherence (future) mean abs diff: {diff:.6f}")

    return bg_test, bg_future
