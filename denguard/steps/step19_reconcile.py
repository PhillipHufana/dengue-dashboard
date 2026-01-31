# ============================================================
# file: denguard/steps/step19_reconcile.py
# (PATCHED) reconcile + grid-fill for UI plotting
# ============================================================
from __future__ import annotations

from typing import Tuple, Optional
import numpy as np
import pandas as pd

from denguard.config import Config
from denguard.forecast_schema import ensure_barangay_forecast_df, ensure_city_forecast_df


# -------------------------
# GRID-FILL all_models_future for consistent UI plotting
# Ensures full grid: all barangays x all future weeks x 4 model series
# -------------------------


def reconcile_forecasts(
    disagg_future: pd.DataFrame,
    local_forecasts_long: pd.DataFrame,
    local_perf: pd.DataFrame,
    city_future: pd.DataFrame,
    cfg: Config,
    keep_all_models: bool = True,
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    print("\n== STEP 19: Forecast Reconciliation (Preferred + Coherent) ==")

    # --- Normalize city_future to schema (tolerant) ---
    if "model_name" not in city_future.columns or "horizon_type" not in city_future.columns:
        city_future = ensure_city_forecast_df(city_future, model_name="city_preferred", horizon_type="future")

    city = city_future[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    city["ds"] = pd.to_datetime(city["ds"], errors="raise")
    city = city.sort_values("ds").reset_index(drop=True)

    disagg = disagg_future.copy()
    disagg = disagg[disagg["horizon_type"] == "future"].copy()

    loc = local_forecasts_long.copy()
    loc = loc[loc["horizon_type"] == "future"].copy() if not loc.empty else loc

    perf = local_perf.copy()
    if "Barangay_key" not in perf.columns or "Chosen" not in perf.columns:
        raise ValueError("local_perf must include columns: Barangay_key, Chosen")

    # --- Choose local series per barangay based on local_perf ---
    if loc.empty:
        chosen_local = loc
    else:
        chosen_map = perf.set_index("Barangay_key")["Chosen"].to_dict()
        loc["chosen_for_bgy"] = loc["Barangay_key"].map(chosen_map)
        chosen_local = loc[loc["model_name"] == loc["chosen_for_bgy"]].drop(columns=["chosen_for_bgy"])

    # ✅ ROBUSTNESS FIX: if chosen_local is empty w/ no columns, prevent KeyError
    needed_local_cols = ["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]
    if chosen_local is None or chosen_local.empty:
        chosen_local = pd.DataFrame(columns=needed_local_cols)

    # Merge disagg + chosen local (local overrides disagg where present)
    base = disagg.merge(
        chosen_local[["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper"]].rename(
            columns={"yhat": "local_yhat", "yhat_lower": "local_yhat_lower", "yhat_upper": "local_yhat_upper"}
        ),
        on=["Barangay_key", "ds"],
        how="left",
    )

    # Preferred = local if present else disagg
    base["yhat_pref"] = base["local_yhat"].combine_first(base["yhat"])
    base["yhat_lower_pref"] = base["local_yhat_lower"].combine_first(base["yhat_lower"])
    base["yhat_upper_pref"] = base["local_yhat_upper"].combine_first(base["yhat_upper"])

    for c in ["yhat_pref", "yhat_lower_pref", "yhat_upper_pref"]:
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0.0).clip(lower=0)

    # --- Coherence scaling: sum(preferred barangays) == city yhat, per ds ---
    sum_bg = base.groupby("ds")["yhat_pref"].sum().rename("sum_barangays").reset_index()
    chk = sum_bg.merge(city[["ds", "yhat"]].rename(columns={"yhat": "city_yhat"}), on="ds", how="inner")
    if len(chk) != len(city):
        raise ValueError("Mismatch in dates between barangay future and city future forecasts.")

    chk["scale"] = chk["city_yhat"] / chk["sum_barangays"].replace(0, np.nan)
    chk["scale"] = chk["scale"].replace([np.inf, -np.inf], np.nan).fillna(1.0)

    scale_map = chk.set_index("ds")["scale"]
    scale_series = base["ds"].map(scale_map).fillna(1.0)

    base["yhat_pref"] = (base["yhat_pref"] * scale_series).clip(lower=0)
    base["yhat_lower_pref"] = (base["yhat_lower_pref"] * scale_series).clip(lower=0)
    base["yhat_upper_pref"] = (base["yhat_upper_pref"] * scale_series).clip(lower=0)

    preferred_raw = base[["Barangay_key", "ds"]].copy()
    preferred_raw["yhat"] = base["yhat_pref"]
    preferred_raw["yhat_lower"] = base["yhat_lower_pref"]
    preferred_raw["yhat_upper"] = base["yhat_upper_pref"]

    # Optional guard (highly recommended)
    if not preferred_raw.columns.is_unique:
        raise ValueError(f"preferred_raw has duplicate columns: {preferred_raw.columns[preferred_raw.columns.duplicated()].tolist()}")

    dupes = base.columns[base.columns.duplicated()].tolist()
    if dupes:
        raise ValueError(f"base has duplicate columns: {dupes}")

    preferred_future = ensure_barangay_forecast_df(preferred_raw, model_name="preferred", horizon_type="future")
    preferred_future.to_csv(cfg.out / "barangay_forecasts_preferred_future_long.csv", index=False)

    # Optional: all models future grid for UI
    all_models_future = None
    if keep_all_models:
        all_models_future = _grid_fill_future_models(
            disagg_future_df=disagg,
            loc_future_df=loc,
            preferred_future_df=preferred_future,
            cfg=cfg,
            city_future=city_future,
        )
        all_models_future.to_csv(cfg.out / "barangay_forecasts_all_models_future_long.csv", index=False)

    # Diagnostic: coherence diff
    rec_sum = preferred_future.groupby("ds")["yhat"].sum().rename("sum_pref").reset_index()
    rec_sum = rec_sum.merge(city[["ds", "yhat"]].rename(columns={"yhat": "city_yhat"}), on="ds", how="left")
    diff = float((rec_sum["sum_pref"] - rec_sum["city_yhat"]).abs().mean())
    print(f"✅ Preferred reconciliation complete. Mean abs diff = {diff:.12f}")

    return preferred_future, all_models_future


def _grid_fill_future_models(
    disagg_future_df: pd.DataFrame,
    loc_future_df: pd.DataFrame,
    preferred_future_df: pd.DataFrame,
    *,
    cfg: Config,
    city_future: pd.DataFrame,
) -> pd.DataFrame:
    from denguard.keys import make_barangay_db_key

    # Canonical barangay keys
    canonical = pd.read_csv(cfg.canon_csv)
    all_keys = canonical["canonical_name"].map(make_barangay_db_key).dropna().unique()

    # Future horizon dates (authoritative)
    all_ds = pd.DatetimeIndex(pd.to_datetime(city_future["ds"], errors="raise")).sort_values()

    # ✅ sanity guard: city ds must be unique
    if all_ds.duplicated().any():
        raise ValueError("city_future ds contains duplicates.")

    model_list = ["disagg", "local_prophet", "local_arima", "preferred"]

    grid = (
        pd.MultiIndex.from_product([all_keys, all_ds, model_list], names=["Barangay_key", "ds", "model_name"])
        .to_frame(index=False)
    )
    grid["horizon_type"] = "future"

    base_cols = ["Barangay_key", "ds", "yhat", "yhat_lower", "yhat_upper", "model_name", "horizon_type"]

    dis = disagg_future_df.copy()
    dis = dis[dis["horizon_type"] == "future"].copy()
    dis = dis[base_cols]

    # ✅ sanity guard: disagg must be labeled correctly
    expected = {"disagg"}
    got = set(dis["model_name"].unique())
    if got - expected:
        print(f"⚠️ disagg contains unexpected model_name values: {sorted(got)}")

    loc = loc_future_df.copy() if loc_future_df is not None else pd.DataFrame(columns=base_cols)
    if not loc.empty:
        loc = loc[loc["horizon_type"] == "future"].copy()
        loc = loc[loc["model_name"].isin(["local_prophet", "local_arima"])].copy()
        loc = loc[base_cols]

    pref = preferred_future_df.copy()
    pref = pref[pref["horizon_type"] == "future"].copy()
    pref = pref[base_cols]

    combined = pd.concat([dis, loc, pref], ignore_index=True)

    out = grid.merge(
        combined,
        on=["Barangay_key", "ds", "model_name", "horizon_type"],
        how="left",
    )

    # status should be based on missingness BEFORE fill
    missing_mask = out["yhat"].isna()

    for c in ["yhat", "yhat_lower", "yhat_upper"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0).clip(lower=0)

    out["status"] = np.where(missing_mask, "filled", "ok")

    # Validate Monday + no duplicates on full long key
    out["ds"] = pd.to_datetime(out["ds"], errors="raise")
    if (out["ds"].dt.dayofweek != 0).any():
        bad = sorted(out.loc[out["ds"].dt.dayofweek != 0, "ds"].unique())
        raise ValueError(f"Grid contains non-Monday ds values: {bad[:10]}")

    if out.duplicated(subset=["Barangay_key", "ds", "model_name", "horizon_type"]).any():
        raise ValueError("Grid has duplicate (Barangay_key, ds, model_name, horizon_type).")
    
    from denguard.forecast_schema import ensure_barangay_forecast_long_df
    out = ensure_barangay_forecast_long_df(out)

    return out.sort_values(["Barangay_key", "model_name", "ds"]).reset_index(drop=True)
