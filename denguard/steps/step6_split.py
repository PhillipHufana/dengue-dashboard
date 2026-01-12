from __future__ import annotations
from typing import Tuple
import pandas as pd
from denguard.config import Config

def train_test_split_city(
    city_weekly: pd.DataFrame,
    cfg: Config
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    print("\n== STEP 6: Train/Test split ==")
    train_end = pd.to_datetime(cfg.train_end_date) if cfg.train_end_date else city_weekly["WeekStart"].max()

    city_prophet = (
        city_weekly.rename(columns={"WeekStart": "ds", "CityCases": "y"})
        .sort_values("ds")
        .reset_index(drop=True)
    )

    train_city = city_prophet[city_prophet["ds"] <= train_end].copy()
    test_city  = city_prophet[city_prophet["ds"] >  train_end].copy()

    if train_city.empty or test_city.empty:
        raise ValueError(
            f"Invalid split around {cfg.train_end_date}. "
            f"train={len(train_city)} test={len(test_city)}"
        )

    print("Train range:", train_city["ds"].min().date(), "→", train_city["ds"].max().date())
    print("Test  range:", test_city["ds"].min().date(),  "→", test_city["ds"].max().date())

    horizon = len(test_city) if cfg.forecast_weeks_override is None else int(cfg.forecast_weeks_override)
    if horizon <= 0:
        raise ValueError("Horizon must be positive.")

    return city_prophet, train_city, test_city, horizon
