from __future__ import annotations

import numpy as np
import pandas as pd
from denguard.utils import smape


def prophet_additional_diagnostics(PROPHET_OK: bool, city_prophet_test: pd.DataFrame, test_city: pd.DataFrame) -> float:
    """
    Expects:
      - city_prophet_test standardized city df with columns: ds, yhat, ...
      - test_city with columns: ds, y
    """
    print("\n== STEP 11: Additional Prophet diagnostics ==")

    if not PROPHET_OK or city_prophet_test is None or city_prophet_test.empty:
        print("⚠️ Prophet model not available; skipping SMAPE diagnostic.")
        return float("nan")

    fc = city_prophet_test.copy()
    fc["ds"] = pd.to_datetime(fc["ds"], errors="raise")
    tc = test_city.copy()
    tc["ds"] = pd.to_datetime(tc["ds"], errors="raise")

    merged = tc.merge(fc[["ds", "yhat"]], on="ds", how="left").dropna(subset=["yhat"])
    if merged.empty:
        print("⚠️ No overlap between Prophet test forecast and test_city.")
        return float("nan")

    low_weeks = merged[merged["y"] < 100]
    smape_val = float(smape(merged["y"], merged["yhat"]))

    print(f"Low-case weeks (<100 cases): {len(low_weeks)} / {len(merged)}")
    print(f"SMAPE (Prophet city test): {smape_val:.3f}")
    return smape_val

