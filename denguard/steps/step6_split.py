from __future__ import annotations
from typing import Tuple
import pandas as pd
from denguard.config import Config
import numpy as np

def train_test_split_city(
    city_weekly: pd.DataFrame,
    cfg: Config
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    print("\n== STEP 6: Train/Test split ==")
    train_end = pd.to_datetime(cfg.train_end_date) if cfg.train_end_date else pd.to_datetime(city_weekly["WeekStart"]).max()

    city_prophet = (
        city_weekly.rename(columns={"WeekStart": "ds", "CityCases": "y"})
        .sort_values("ds")
        .reset_index(drop=True)
    )
    city_prophet["ds"] = pd.to_datetime(city_prophet["ds"], errors="raise")

    train_city = city_prophet[city_prophet["ds"] <= train_end].copy()
    test_city  = city_prophet[city_prophet["ds"] >  train_end].copy()

    if train_city.empty or test_city.empty:
        raise ValueError(
            f"Invalid split around {cfg.train_end_date}. "
            f"train={len(train_city)} test={len(test_city)}"
        )

    print("Train range:", train_city["ds"].min().date(), "→", train_city["ds"].max().date())
    print("Test  range:", test_city["ds"].min().date(),  "→", test_city["ds"].max().date())

    print("train_city y min/mean/max:", train_city["y"].min(), train_city["y"].mean(), train_city["y"].max())
    print("test_city  y min/mean/max:", test_city["y"].min(), test_city["y"].mean(), test_city["y"].max())

    test_len = len(test_city)

    assert train_city["ds"].max() <= train_end
    assert test_city["ds"].min() > train_end

    # Reconstruct and verify equality
    recon = pd.concat([train_city, test_city]).sort_values("ds").reset_index(drop=True)
    orig = city_prophet.sort_values("ds").reset_index(drop=True)
    assert len(recon) == len(orig)
    assert recon["ds"].equals(orig["ds"])
    assert np.allclose(recon["y"].to_numpy(), orig["y"].to_numpy())

    return city_prophet, train_city, test_city, test_len
