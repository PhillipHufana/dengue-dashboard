from __future__ import annotations
import numpy as np
import pandas as pd
from denguard.utils import smape

def prophet_additional_diagnostics(PROPHET_OK: bool, forecast_prophet, test_city: pd.DataFrame) -> float:
    print("\n== STEP 11: Additional Prophet diagnostics ==")
    avg_smape = np.nan
    if PROPHET_OK and forecast_prophet is not None:
        merged_prophet = test_city.merge(forecast_prophet[["ds", "yhat"]], on="ds", how="left")
        low_weeks = merged_prophet[merged_prophet["y"] < 100]
        smape_val = smape(merged_prophet["y"], merged_prophet["yhat"])
        avg_smape = float(smape_val)
        print(f"Low-case weeks (<100 cases): {len(low_weeks)} / {len(merged_prophet)}")
        print(f"SMAPE (Prophet): {smape_val:.3f}")
    else:
        print("⚠️ Prophet model not available; skipping SMAPE diagnostic.")
    return avg_smape
