from __future__ import annotations
from typing import Tuple
import numpy as np
import pandas as pd
from denguard.config import Config
from denguard.keys import make_barangay_db_key
from denguard.forecast_schema import ensure_barangay_forecast_df


def hybrid_disaggregation(
    city_test: pd.DataFrame,     # standardized city TEST forecast
    city_future: pd.DataFrame,   # standardized city FUTURE forecast
    weekly_full: pd.DataFrame,
    cfg: Config,
    alpha_smooth: float = 1.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Top-down disaggregation using train-window proportions.
    Returns standardized barangay forecasts for test and future with model_name='disagg'.
    """
    print("\n== STEP 10: Hybrid top-down disaggregation (standardized) ==")

    train_end = pd.to_datetime(cfg.train_end_date)
    recent_start = pd.to_datetime(cfg.recent_weight_start)

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

    # Smooth to avoid all-zero / permanent zero weights
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

    bg_test = _disagg(city_test, "test")
    bg_future = _disagg(city_future, "future")

    # Validate coherence on each horizon separately
    for name, bg, city in [("test", bg_test, city_test), ("future", bg_future, city_future)]:
        s = bg.groupby("ds")["yhat"].sum().reset_index()
        chk = s.merge(city[["ds", "yhat"]], on="ds", how="left", suffixes=("_sum", "_city"))
        diff = float((chk["yhat_sum"] - chk["yhat_city"]).abs().mean())
        print(f"✅ Disagg coherence ({name}) mean abs diff: {diff:.6f}")

    return bg_test, bg_future
