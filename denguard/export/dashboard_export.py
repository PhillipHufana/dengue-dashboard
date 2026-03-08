# denguard/export/dashboard_export.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def safe_read_csv(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        print(f"Missing file: {path}")
        return None
    try:
        return pd.read_csv(path)
    except Exception as e:
        print(f"Failed to read {path}: {e}")
        return None


def _standardize_long_forecast(
    df: Optional[pd.DataFrame],
    *,
    key_candidates: tuple[str, ...] = ("Barangay_key", "name"),
    ds_candidates: tuple[str, ...] = ("ds", "week_start"),
) -> Optional[pd.DataFrame]:
    if df is None:
        return None

    out = df.copy()
    rename_map = {}

    if "Barangay_key" not in out.columns:
        for c in key_candidates:
            if c in out.columns:
                rename_map[c] = "Barangay_key"
                break

    if "ds" not in out.columns:
        for c in ds_candidates:
            if c in out.columns:
                rename_map[c] = "ds"
                break

    if rename_map:
        out = out.rename(columns=rename_map)

    if "ds" in out.columns:
        out["ds"] = pd.to_datetime(out["ds"], errors="coerce")
        out = out.dropna(subset=["ds"])

    if "Barangay_key" in out.columns:
        out["Barangay_key"] = out["Barangay_key"].astype(str).str.strip().str.lower()

    return out


def produce_dashboard_forecast(cfg) -> pd.DataFrame:
    """
    Produce a dashboard-friendly CSV from the current pipeline outputs.

    Preferred barangay forecasts are used as the base series. If the all-models
    long file is present, disagg and local comparison series are merged in too.
    """
    outdir = Path(cfg.out)
    outdir.mkdir(parents=True, exist_ok=True)

    preferred_fp = outdir / "barangay_forecasts_preferred_future_long.csv"
    all_models_fp = outdir / "barangay_forecasts_all_models_future_long.csv"
    all_models_alt_fp = outdir / "barangay_forecasts_long.csv"
    city_fp = outdir / "city_forecasts_long.csv"
    city_future_fp = outdir / "city_forecasts_future.csv"
    eligibility_fp = outdir / "local_eligibility.csv"
    case_counts_fp = outdir / "barangay_case_counts.csv"

    preferred_df = _standardize_long_forecast(safe_read_csv(preferred_fp))
    all_models_df = _standardize_long_forecast(safe_read_csv(all_models_fp))
    if all_models_df is None:
        all_models_df = _standardize_long_forecast(safe_read_csv(all_models_alt_fp))

    city_df = safe_read_csv(city_fp)
    if city_df is None:
        city_df = safe_read_csv(city_future_fp)

    eligibility_df = safe_read_csv(eligibility_fp)
    counts_df = safe_read_csv(case_counts_fp)

    if preferred_df is None and all_models_df is not None and "model_name" in all_models_df.columns:
        preferred_df = all_models_df[all_models_df["model_name"].astype(str).str.lower() == "preferred"].copy()

    if preferred_df is None or preferred_df.empty:
        raise FileNotFoundError(
            "No preferred barangay forecast output found. "
            "Expected barangay_forecasts_preferred_future_long.csv or preferred rows in the all-models file."
        )

    if "horizon_type" in preferred_df.columns:
        preferred_df = preferred_df[preferred_df["horizon_type"].astype(str).str.lower() == "future"].copy()

    base = preferred_df[["Barangay_key", "ds"]].copy()
    base["Forecast_Final"] = pd.to_numeric(preferred_df["yhat"], errors="coerce")

    if all_models_df is not None and not all_models_df.empty and "model_name" in all_models_df.columns:
        if "horizon_type" in all_models_df.columns:
            all_models_df = all_models_df[all_models_df["horizon_type"].astype(str).str.lower() == "future"].copy()

        pivot = (
            all_models_df.pivot_table(
                index=["Barangay_key", "ds"],
                columns="model_name",
                values="yhat",
                aggfunc="last",
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )
        pivot = pivot.rename(
            columns={
                "disagg": "Forecast_Hybrid",
                "local_prophet": "LocalProphetForecast",
                "local_arima": "LocalArimaForecast",
                "preferred": "Forecast_Final_from_all_models",
            }
        )
        base = base.merge(pivot, on=["Barangay_key", "ds"], how="left")

    if "Forecast_Hybrid" not in base.columns:
        base["Forecast_Hybrid"] = np.nan
    if "LocalProphetForecast" not in base.columns:
        base["LocalProphetForecast"] = np.nan
    if "LocalArimaForecast" not in base.columns:
        base["LocalArimaForecast"] = np.nan

    base["local_forecast"] = base["LocalProphetForecast"].combine_first(base["LocalArimaForecast"])

    if city_df is not None:
        city_df = city_df.copy()
        if "week_start" in city_df.columns and "ds" not in city_df.columns:
            city_df = city_df.rename(columns={"week_start": "ds"})
        city_df["ds"] = pd.to_datetime(city_df["ds"], errors="coerce")
        city_df = city_df.dropna(subset=["ds"])

        if "horizon_type" in city_df.columns:
            city_df = city_df[city_df["horizon_type"].astype(str).str.lower() == "future"].copy()

        if "CityForecast" not in city_df.columns and "yhat" in city_df.columns:
            city_df = city_df.rename(columns={"yhat": "CityForecast"})
        if "ModelUsed" not in city_df.columns and "model_name" in city_df.columns:
            city_df = city_df.rename(columns={"model_name": "ModelUsed"})

        city_small = city_df[["ds", "CityForecast", "ModelUsed"]].drop_duplicates(subset=["ds"], keep="last")
        base = base.merge(city_small, on="ds", how="left")
    else:
        base["CityForecast"] = np.nan
        base["ModelUsed"] = None

    if counts_df is not None:
        counts_df = counts_df.copy()
        counts_df["Barangay_key"] = counts_df["Barangay_key"].astype(str).str.strip().str.lower()
        counts_df = counts_df.rename(columns={"CaseCount": "TotalCases"})
        base = base.merge(counts_df[["Barangay_key", "TotalCases"]], on="Barangay_key", how="left")
    else:
        base["TotalCases"] = np.nan

    if eligibility_df is not None:
        eligibility_df = eligibility_df.copy()
        eligibility_df["Barangay_key"] = eligibility_df["Barangay_key"].astype(str).str.strip().str.lower()

        keep_cols = ["Barangay_key"]
        if "eligible_local" in eligibility_df.columns:
            keep_cols.append("eligible_local")
        if "eligibility_reason" in eligibility_df.columns:
            keep_cols.append("eligibility_reason")

        base = base.merge(eligibility_df[keep_cols], on="Barangay_key", how="left")
        base = base.rename(columns={"eligible_local": "LocalEligible", "eligibility_reason": "EligibilityReason"})
    else:
        base["LocalEligible"] = np.nan
        base["EligibilityReason"] = None

    base["Tier"] = np.nan

    if base["TotalCases"].notna().any():
        totals = base[["Barangay_key", "TotalCases"]].drop_duplicates()
        total_cases = totals["TotalCases"].sum()
        if total_cases and total_cases > 0:
            prop_map = (totals.set_index("Barangay_key")["TotalCases"] / total_cases).to_dict()
            base["Proportion_train"] = base["Barangay_key"].map(prop_map).fillna(0.0)
        else:
            base["Proportion_train"] = 0.0
    else:
        base["Proportion_train"] = 0.0

    final_cols = [
        "Barangay_key",
        "ds",
        "Forecast_Final",
        "Forecast_Hybrid",
        "local_forecast",
        "LocalProphetForecast",
        "LocalArimaForecast",
        "CityForecast",
        "ModelUsed",
        "TotalCases",
        "Tier",
        "LocalEligible",
        "EligibilityReason",
        "Proportion_train",
    ]

    for c in final_cols:
        if c not in base.columns:
            base[c] = np.nan

    out = base[final_cols].sort_values(["Barangay_key", "ds"]).reset_index(drop=True)

    csv_path = outdir / "dashboard_forecast.csv"
    out.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"Dashboard CSV written: {csv_path}")
    return out


if __name__ == "__main__":
    try:
        from denguard.config import DEFAULT_CFG as _CFG

        cfgobj = _CFG
    except Exception:
        raise SystemExit("Please call produce_dashboard_forecast(cfg) from your pipeline with the Config object.")

    produce_dashboard_forecast(cfgobj)
