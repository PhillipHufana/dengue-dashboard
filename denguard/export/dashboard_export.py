# denguard/export/dashboard_export.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Attempt optional geo support
try:
    import geopandas as gpd  # type: ignore
    GEOPANDAS_OK = True
except Exception:
    GEOPANDAS_OK = False


def safe_read_csv(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        print(f"⚠️ Missing file: {path}")
        return None
    try:
        return pd.read_csv(path)
    except Exception as e:
        print(f"⚠️ Failed to read {path}: {e}")
        return None


def produce_dashboard_forecast(cfg) -> pd.DataFrame:
    """
    Produce a single merged CSV (dashboard_forecast.csv) containing:
      - Barangay_key, ds (date), Final (reconciled), Forecast (hybrid),
        local_forecast, CityForecast (city-level), ModelUsed, Tier, TotalCases, Proportion
      - Optional geometry if geopandas and geojsons are present.

    Saves: cfg.out / "dashboard_forecast.csv"
    Returns the merged DataFrame.
    """
    outdir = Path(cfg.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # load canonical pipeline outputs (some may be absent depending on when called)
    final_fp = outdir / "barangay_forecasts_final.csv"
    hybrid_fp = outdir / "barangay_forecasts_hybrid.csv"
    local_fp = outdir / "barangay_local_forecasts.csv"
    city_fp = outdir / "city_forecasts.csv"
    tiers_fp = outdir / "barangay_tiers.csv"
    case_counts_fp = outdir / "barangay_case_counts.csv"

    final_df = safe_read_csv(final_fp)
    hybrid_df = safe_read_csv(hybrid_fp)
    local_df = safe_read_csv(local_fp)
    city_df = safe_read_csv(city_fp)
    tiers_df = safe_read_csv(tiers_fp)
    counts_df = safe_read_csv(case_counts_fp)

    # -- normalize columns & minimal schemas --
    # final_df expected: Barangay_key, ds, Final, Forecast, local_forecast (maybe)
    # hybrid_df expected: Barangay_key, ds, Forecast, Forecast_lower, Forecast_upper
    # local_df expected: Barangay_key, ds, local_forecast
    # city_df expected: ds, CityForecast, ModelUsed (maybe)
    # tiers_df expected: Barangay, TotalCases, Tier
    # counts_df expected: Barangay_key, CaseCount

    # If final_df missing, try to construct a usable base from hybrid (+ local)
    base: pd.DataFrame
    if final_df is not None:
        # unify dtype for date
        final_df["ds"] = pd.to_datetime(final_df["ds"])
        base = final_df.rename(columns={"Final": "Forecast_Final", "Forecast": "Forecast_Hybrid"})
    elif hybrid_df is not None:
        hybrid_df["ds"] = pd.to_datetime(hybrid_df["ds"])
        base = hybrid_df.rename(columns={"Forecast": "Forecast_Hybrid"})
        base["Forecast_Final"] = base["Forecast_Hybrid"]
    else:
        raise FileNotFoundError("Neither final nor hybrid forecast files found. Cannot produce dashboard table.")

    # ensure keys
    base["Barangay_key"] = base["Barangay_key"].astype(str).str.strip().str.lower()

    # merge hybrid (if exists) to ensure Forecast_Hybrid present
    if hybrid_df is not None and "Forecast_Hybrid" not in base.columns:
        hybrid_df["ds"] = pd.to_datetime(hybrid_df["ds"])
        base = base.merge(
            hybrid_df[["Barangay_key", "ds", "Forecast"]],
            on=["Barangay_key", "ds"],
            how="left"
        ).rename(columns={"Forecast": "Forecast_Hybrid"})

    # merge local forecasts
    if local_df is not None:
        local_df["ds"] = pd.to_datetime(local_df["ds"])
        local_df["Barangay_key"] = local_df["Barangay_key"].astype(str).str.strip().str.lower()
        base = base.merge(
            local_df[["Barangay_key", "ds", "local_forecast"]],
            on=["Barangay_key", "ds"],
            how="left",
        )

    # merge city-level forecast (CityForecast) by ds
    if city_df is not None:
        city_df["ds"] = pd.to_datetime(city_df["ds"])
        # standardize column name
        if "CityForecast" not in city_df.columns and "yhat" in city_df.columns:
            city_df = city_df.rename(columns={"yhat": "CityForecast"})
        city_small = city_df[["ds", "CityForecast", "ModelUsed"]].drop_duplicates(subset=["ds"])
        base = base.merge(city_small, on="ds", how="left")
    else:
        base["CityForecast"] = np.nan
        base["ModelUsed"] = None

    # merge tier/totalcases
    if tiers_df is not None:
        tiers_df = tiers_df.rename(columns={"Barangay": "Barangay_key"})
        tiers_df["Barangay_key"] = tiers_df["Barangay_key"].astype(str).str.strip().str.lower()
        base = base.merge(tiers_df[["Barangay_key", "TotalCases", "Tier"]], on="Barangay_key", how="left")
    elif counts_df is not None:
        counts_df["Barangay_key"] = counts_df["Barangay_key"].astype(str).str.strip().str.lower()
        counts_df = counts_df.rename(columns={"CaseCount": "TotalCases"})
        base = base.merge(counts_df[["Barangay_key", "TotalCases"]], on="Barangay_key", how="left")
        base["Tier"] = None
    else:
        base["TotalCases"] = np.nan
        base["Tier"] = None

    # compute proportion within training window if TotalCases exists
    if "TotalCases" in base.columns and base["TotalCases"].notna().any():
        total = base[["Barangay_key", "TotalCases"]].drop_duplicates()["TotalCases"].sum()
        if total and total > 0:
            prop_map = (base[["Barangay_key", "TotalCases"]].drop_duplicates().set_index("Barangay_key")["TotalCases"] / total).to_dict()
            base["Proportion_train"] = base["Barangay_key"].map(prop_map).fillna(0.0)
        else:
            base["Proportion_train"] = 0.0
    else:
        base["Proportion_train"] = 0.0

    # metadata columns & ordering
    # prefer Final if available
    if "Forecast_Final" not in base.columns:
        base["Forecast_Final"] = base.get("local_forecast", base.get("Forecast_Hybrid", np.nan))

    final_cols = [
        "Barangay_key", "ds",
        "Forecast_Final", "Forecast_Hybrid", "local_forecast",
        "CityForecast", "ModelUsed",
        "TotalCases", "Tier", "Proportion_train"
    ]
    for c in final_cols:
        if c not in base.columns:
            base[c] = np.nan

    out = base[final_cols].copy()
    out = out.sort_values(["Barangay_key", "ds"]).reset_index(drop=True)

    # attempt geo join if geopandas present and geojson(s) exist in working directory
    geo_added = False
    if GEOPANDAS_OK:
        # check typical uploaded geojson names (you provided two earlier)
        candidates = [
            Path("/mnt/data/DAVAO_Points_geo.geojson"),
            Path("/mnt/data/DAVAO_Poly_geo.geojson"),
            Path("DAVAO_Points_geo.geojson"),
            Path("DAVAO_Poly_geo.geojson"),
            cfg.canon_csv  # sometimes canonical CSV contains geometry? unlikely
        ]
        for c in candidates:
            if c is None:
                continue
            if isinstance(c, Path) and c.exists():
                try:
                    gdf = gpd.read_file(c)
                    # try to find common join key: canonical_name or barangay name column
                    lower_cols = [col.lower() for col in gdf.columns]
                    join_col = None
                    for candidate_col in ["canonical_name", "name", "barangay", "brgy", "brgy_name"]:
                        if candidate_col in lower_cols:
                            join_col = gdf.columns[lower_cols.index(candidate_col)]
                            break
                    # if no textual join, try point centroid mapping later; otherwise skip
                    if join_col:
                        gdf[join_col] = gdf[join_col].astype(str).str.strip().str.lower()
                        out = out.merge(gdf[[join_col, "geometry"]].rename(columns={join_col: "Barangay_key"}), on="Barangay_key", how="left")
                        geo_added = True
                        print(f"✅ Geo joined using {c} on {join_col}")
                        break
                except Exception as e:
                    print(f"⚠️ Failed to read/join geo file {c}: {e}")
    else:
        # geopandas not available
        pass

    # write CSV (geometry will be dropped automatically by pandas if present)
    csv_path = outdir / "dashboard_forecast.csv"
    try:
        # if a geometry column exists, attempt to store WKT (optional)
        if "geometry" in out.columns:
            try:
                out["geometry_wkt"] = out["geometry"].apply(lambda g: g.wkt if g is not None else None)
            except Exception:
                out = out.drop(columns=["geometry"])
        out.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"✅ Dashboard CSV written: {csv_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to write dashboard csv: {e}")

    return out


# helper CLI-like entry
if __name__ == "__main__":
    # try to import local config if available
    try:
        from denguard.config import DEFAULT_CFG as _CFG  # type: ignore
        cfgobj = _CFG
    except Exception:
        raise SystemExit("Please call produce_dashboard_forecast(cfg) from your pipeline with the Config object.")
    produce_dashboard_forecast(cfgobj)
