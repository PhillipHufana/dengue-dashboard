from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from denguard.config import Config
from denguard.forecast_schema import ensure_barangay_forecast_df
from denguard.keys import make_barangay_db_key


def _load_all_barangay_keys(cfg: Config) -> np.ndarray:
    canonical = pd.read_csv(cfg.canon_csv)
    return canonical["canonical_name"].map(make_barangay_db_key).dropna().unique()


def _normalize_weights(case_df: pd.DataFrame, all_keys: np.ndarray, alpha_smooth: float) -> pd.DataFrame:
    w = (
        case_df.groupby("Barangay_key")["Cases"].sum()
        .reindex(all_keys, fill_value=0.0)
        .rename_axis("Barangay_key")
        .reset_index(name="Cases")
    )
    w["Cases_smoothed"] = pd.to_numeric(w["Cases"], errors="coerce").fillna(0.0).astype(float) + float(alpha_smooth)
    total = float(w["Cases_smoothed"].sum())
    if total <= 0:
        raise ValueError("Cannot compute disaggregation weights: total smoothed cases <= 0")
    w["p"] = w["Cases_smoothed"] / total
    return w[["Barangay_key", "Cases", "p"]]


def _compute_weight_table(
    *,
    weekly_full: pd.DataFrame,
    cfg: Config,
    train_end: pd.Timestamp,
    all_keys: np.ndarray,
    scheme: str,
    alpha_smooth: float,
) -> tuple[pd.DataFrame, pd.Timestamp | None, pd.Timestamp | None]:
    train = weekly_full[pd.to_datetime(weekly_full["WeekStart"], errors="coerce") <= train_end].copy()
    train["WeekStart"] = pd.to_datetime(train["WeekStart"], errors="coerce")
    train = train.dropna(subset=["WeekStart"])
    if train.empty:
        raise ValueError("No train history available for disaggregation.")

    scheme = str(scheme).lower().strip()
    window_start = train["WeekStart"].min()
    window_end = train["WeekStart"].max()
    window_weeks = int(getattr(cfg, "disagg_weight_weeks", 52))

    if scheme == "static":
        w = _normalize_weights(train, all_keys, alpha_smooth)
        w["month"] = np.nan
        return w, window_start, window_end

    if scheme == "rolling":
        if window_weeks <= 0:
            raise ValueError(f"disagg_weight_weeks must be positive, got {window_weeks}")
        recent_start = train_end - pd.Timedelta(weeks=window_weeks - 1)
        recent = train[train["WeekStart"] >= recent_start].copy()
        if recent.empty:
            recent = train
        w = _normalize_weights(recent, all_keys, alpha_smooth)
        w["month"] = np.nan
        return w, recent["WeekStart"].min(), recent["WeekStart"].max()

    if scheme in {"seasonal", "hybrid"}:
        season_rows = []
        rolling_global = None
        if scheme == "hybrid":
            recent_start = train_end - pd.Timedelta(weeks=max(window_weeks, 1) - 1)
            recent = train[train["WeekStart"] >= recent_start].copy()
            if recent.empty:
                recent = train
            rolling_global = _normalize_weights(recent, all_keys, alpha_smooth)[["Barangay_key", "p"]].rename(
                columns={"p": "p_roll"}
            )

        for m in range(1, 13):
            mdf = train[train["WeekStart"].dt.month == m].copy()
            if mdf.empty:
                mdf = train
            w_m = _normalize_weights(mdf, all_keys, alpha_smooth)
            w_m["month"] = m
            season_rows.append(w_m)

        seasonal = pd.concat(season_rows, ignore_index=True)
        if scheme == "seasonal":
            return seasonal, window_start, window_end

        lam = float(getattr(cfg, "disagg_hybrid_lambda", 0.5))
        lam = float(np.clip(lam, 0.0, 1.0))
        out = seasonal.merge(rolling_global, on="Barangay_key", how="left")
        out["p_roll"] = pd.to_numeric(out["p_roll"], errors="coerce").fillna(0.0)
        out["p"] = lam * pd.to_numeric(out["p"], errors="coerce").fillna(0.0) + (1.0 - lam) * out["p_roll"]
        out["p"] = out["p"].clip(lower=0.0)
        out = out.drop(columns=["p_roll"])
        out["p"] = out["p"] / out.groupby("month")["p"].transform("sum")
        return out[["Barangay_key", "Cases", "p", "month"]], window_start, window_end

    raise ValueError(f"Unsupported disagg scheme: {scheme}")


def hybrid_disaggregation(
    city_test: pd.DataFrame,
    city_future: pd.DataFrame,
    weekly_full: pd.DataFrame,
    cfg: Config,
    *,
    train_end: pd.Timestamp,
    alpha_smooth: float = 1.0,
    scheme: str = "rolling",
    weights_csv_name: str = "disagg_weights.csv",
    write_weights_csv: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Top-down disaggregation with configurable proportion scheme.

    Supported schemes:
      - static: global train-history proportions
      - rolling: recent-window proportions (cfg.disagg_weight_weeks)
      - seasonal: month-specific proportions from train history
      - hybrid: blend seasonal + rolling (cfg.disagg_hybrid_lambda)
    """
    print(f"\n== STEP 10: Top-down disaggregation ({scheme}) ==")

    train_end = pd.to_datetime(train_end)
    all_keys = _load_all_barangay_keys(cfg)
    weights_tbl, window_start, window_end = _compute_weight_table(
        weekly_full=weekly_full,
        cfg=cfg,
        train_end=train_end,
        all_keys=all_keys,
        scheme=scheme,
        alpha_smooth=alpha_smooth,
    )

    if write_weights_csv:
        out = weights_tbl.rename(columns={"Barangay_key": "barangay", "Cases": "cases_in_window", "p": "weight"}).copy()
        out["window_start"] = window_start
        out["window_end"] = window_end
        out["alpha_smooth"] = float(alpha_smooth)
        out["scheme"] = str(scheme)
        out["run_id"] = cfg.run_id
        cols = ["barangay", "weight", "cases_in_window", "window_start", "window_end", "alpha_smooth", "scheme", "run_id"]
        if "month" in out.columns:
            cols.insert(1, "month")
        out = out[cols]
        out.to_csv(cfg.out / weights_csv_name, index=False)

    static_w = weights_tbl[["Barangay_key", "p"]].copy() if "month" not in weights_tbl.columns else None

    def _disagg(city_df: pd.DataFrame, horizon_type: str) -> pd.DataFrame:
        if city_df is None or city_df.empty:
            return pd.DataFrame(columns=["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"])

        base = city_df.copy()
        base["ds"] = pd.to_datetime(base["ds"], errors="coerce")
        base = base.dropna(subset=["ds"]).copy()
        if base.empty:
            return pd.DataFrame(columns=["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"])

        if "month" in weights_tbl.columns and weights_tbl["month"].notna().any():
            w = weights_tbl[["Barangay_key", "month", "p"]].copy()
            base["month"] = base["ds"].dt.month
            out = base.merge(w, on="month", how="left")
            if out["p"].isna().any():
                fb = static_w if static_w is not None else _normalize_weights(weekly_full, all_keys, alpha_smooth)[["Barangay_key", "p"]]
                miss = out[out["p"].isna()].drop(columns=["Barangay_key"], errors="ignore")
                miss = miss.drop(columns=["p"], errors="ignore")
                miss["key"] = 1
                fb2 = fb.copy()
                fb2["key"] = 1
                miss = miss.merge(fb2, on="key", how="left").drop(columns=["key"])
                ok = out[out["p"].notna()].copy()
                out = pd.concat([ok, miss], ignore_index=True)
            out = out.drop(columns=["month"], errors="ignore")
        else:
            w = (static_w if static_w is not None else weights_tbl[["Barangay_key", "p"]]).copy()
            base["key"] = 1
            w["key"] = 1
            out = base.merge(w, on="key", how="left").drop(columns=["key"])

        for c in ["yhat", "yhat_lower", "yhat_upper"]:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0) * pd.to_numeric(out["p"], errors="coerce").fillna(0.0)

        out = out[["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        return ensure_barangay_forecast_df(out, model_name="disagg", horizon_type=horizon_type)

    bg_test = _disagg(city_test, "test")
    bg_future = _disagg(city_future, "future")

    if not bg_test.empty and city_test is not None and not city_test.empty:
        s = bg_test.groupby("ds")["yhat"].sum().reset_index()
        chk = s.merge(city_test[["ds", "yhat"]], on="ds", how="left", suffixes=("_sum", "_city"))
        diff = float((chk["yhat_sum"] - chk["yhat_city"]).abs().mean())
        print(f"Disagg coherence (test) mean abs diff: {diff:.6f}")

    if not bg_future.empty and city_future is not None and not city_future.empty:
        s = bg_future.groupby("ds")["yhat"].sum().reset_index()
        chk = s.merge(city_future[["ds", "yhat"]], on="ds", how="left", suffixes=("_sum", "_city"))
        diff = float((chk["yhat_sum"] - chk["yhat_city"]).abs().mean())
        print(f"Disagg coherence (future) mean abs diff: {diff:.6f}")

    return bg_test, bg_future
