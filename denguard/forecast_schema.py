from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd


CITY_COLS = ["ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]
BARA_COLS = ["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]


def _to_dt_monday(s: pd.Series, name: str) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce")
    if dt.isna().any():
        raise ValueError(f"{name}: contains invalid dates (NaT).")
    dow = dt.dt.dayofweek.unique()
    if len(dow) and not np.all(dow == 0):
        raise ValueError(f"{name}: contains non-Monday dates. dayofweek={sorted(map(int, dow))}")
    return dt


def _ensure_interval_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "yhat_lower" not in df.columns:
        df["yhat_lower"] = df["yhat"]
    if "yhat_upper" not in df.columns:
        df["yhat_upper"] = df["yhat"]
    df["yhat"] = pd.to_numeric(df["yhat"], errors="coerce").fillna(0.0).clip(lower=0)
    df["yhat_lower"] = pd.to_numeric(df["yhat_lower"], errors="coerce").fillna(df["yhat"]).clip(lower=0)
    df["yhat_upper"] = pd.to_numeric(df["yhat_upper"], errors="coerce").fillna(df["yhat"]).clip(lower=0)
    return df


def ensure_city_forecast_df(
    df: pd.DataFrame,
    model_name: str,
    horizon_type: str,
) -> pd.DataFrame:
    """
    Enforce city forecast schema:
    ds, yhat, yhat_lower, yhat_upper, model_name, horizon_type
    """
    if not {"ds", "yhat"}.issubset(df.columns):
        raise ValueError("City forecast must include at least ['ds','yhat'].")

    out = df.copy()
    out["ds"] = _to_dt_monday(out["ds"], "city_forecast.ds")

    out = _ensure_interval_cols(out)
    out["model_name"] = model_name
    out["horizon_type"] = horizon_type

    out = out[["ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]].sort_values("ds")
    if out["ds"].duplicated().any():
        raise ValueError("City forecast has duplicate ds.")
    return out.reset_index(drop=True)


def ensure_barangay_forecast_df(
    df: pd.DataFrame,
    model_name: str,
    horizon_type: str,
) -> pd.DataFrame:
    """
    Enforce barangay forecast schema (LONG):
    Barangay_key, ds, yhat, yhat_lower, yhat_upper, model_name, horizon_type
    """
    required = {"Barangay_key", "ds", "yhat"}
    if not required.issubset(df.columns):
        raise ValueError(f"Barangay forecast missing required columns: {sorted(required)}")

    out = df.copy()
    out["ds"] = _to_dt_monday(out["ds"], "barangay_forecast.ds")

    out = _ensure_interval_cols(out)
    out["model_name"] = model_name
    out["horizon_type"] = horizon_type

    out = out[["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]]
    out = out.sort_values(["Barangay_key", "model_name", "ds"]).reset_index(drop=True)

    # ✅ IMPORTANT: uniqueness must include model_name + horizon_type for long format
    if out.duplicated(subset=["Barangay_key", "ds", "model_name", "horizon_type"]).any():
        raise ValueError("Barangay forecast has duplicate (Barangay_key, ds, model_name, horizon_type).")

    return out

def ensure_barangay_forecast_long_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enforce LONG barangay forecast schema (multi-model):
      Barangay_key, ds, yhat, yhat_lower, yhat_upper, model_name, horizon_type
    Validates uniqueness on:
      (Barangay_key, ds, model_name, horizon_type)
    Preserves extra columns (e.g., status) WITHOUT misalignment.
    """
    required = {"Barangay_key", "ds", "yhat", "model_name", "horizon_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Barangay LONG forecast missing required columns: {sorted(missing)}")

    out = df.copy()

    core_cols = ["Barangay_key","ds","yhat","yhat_lower","yhat_upper","model_name","horizon_type"]
    extra_cols = [c for c in out.columns if c not in core_cols]

    # Normalize ds + intervals
    out["ds"] = _to_dt_monday(out["ds"], "barangay_forecast_long.ds")
    out = _ensure_interval_cols(out)

    # ✅ Sort the WHOLE frame once so extras stay aligned
    sort_cols = ["Barangay_key", "model_name", "horizon_type", "ds"]
    out = out.sort_values(sort_cols).reset_index(drop=True)

    # Uniqueness on the long key
    if out.duplicated(subset=["Barangay_key","ds","model_name","horizon_type"]).any():
        raise ValueError("Barangay LONG forecast has duplicate (Barangay_key, ds, model_name, horizon_type).")

    # Return core + extras (aligned)
    return out[core_cols + extra_cols]






def prophet_split_test_future(
    prophet_forecast_full: pd.DataFrame,
    test_ds: pd.DatetimeIndex,
    future_ds: pd.DatetimeIndex,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split Prophet full forecast into test-aligned and future-aligned frames.
    Requires columns: ds, yhat (optionally yhat_lower/yhat_upper).
    """
    if "ds" not in prophet_forecast_full.columns or "yhat" not in prophet_forecast_full.columns:
        raise ValueError("Prophet forecast must include ['ds','yhat'].")

    full = prophet_forecast_full.copy()
    full["ds"] = pd.to_datetime(full["ds"], errors="coerce")
    full = full.dropna(subset=["ds"]).set_index("ds").sort_index()

    test = full.reindex(test_ds)[["yhat"] + [c for c in ["yhat_lower", "yhat_upper"] if c in full.columns]].reset_index()
    fut = full.reindex(future_ds)[["yhat"] + [c for c in ["yhat_lower", "yhat_upper"] if c in full.columns]].reset_index()

    # Rename index column back to ds if it became "index"
    if "index" in test.columns and "ds" not in test.columns:
        test = test.rename(columns={"index": "ds"})
    if "index" in fut.columns and "ds" not in fut.columns:
        fut = fut.rename(columns={"index": "ds"})

    return test, fut


def arima_pred_to_city_df(pred_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert your ARIMA pred_df (index=ds, columns yhat/yhat_lower/yhat_upper) into city forecast df with ds column.
    """
    if not isinstance(pred_df, pd.DataFrame) or "yhat" not in pred_df.columns:
        raise ValueError("ARIMA pred_df must be a DataFrame with column 'yhat' and index=ds.")

    out = pred_df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, errors="coerce")
    if out.index.isna().any():
        raise ValueError("ARIMA pred_df index contains invalid ds.")
    out = out.reset_index().rename(columns={"index": "ds"})
    return out

