from __future__ import annotations
from typing import Tuple
import numpy as np
import pandas as pd
from denguard.config import Config


def train_test_split_city(
    city_weekly: pd.DataFrame,
    cfg: Config,
    *,
    train_end: pd.Timestamp | None = None,
    require_test: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    print("\n== STEP 6: Train/Test split ==")

    # Build a common model-ready city series in ds/y format.
    city_model_df = (
        city_weekly.rename(columns={"WeekStart": "ds", "CityCases": "y"})
        .sort_values("ds")
        .reset_index(drop=True)
    )
    city_model_df["ds"] = pd.to_datetime(city_model_df["ds"], errors="raise")
    city_model_df["y"] = pd.to_numeric(city_model_df["y"], errors="coerce").fillna(0.0)

    # Determine train_end:
    # - Backtest: typically cfg.train_end_date (fixed cutoff)
    # - Production: train_end can be last observed week (pass train_end=None + require_test=False)
    if train_end is None:
        # Backtest default: cfg.backtest_end_date
        # Production default (require_test=False): latest observed
        if getattr(cfg, "run_kind", "backtest") == "backtest":
            train_end = pd.to_datetime(getattr(cfg, "backtest_end_date"))
        else:
            train_end = city_model_df["ds"].max()

    train_city = city_model_df[city_model_df["ds"] <= train_end][["ds", "y"]].copy()
    test_city  = city_model_df[city_model_df["ds"] >  train_end][["ds", "y"]].copy()

    if train_city.empty:
        raise ValueError(
            f"Train set is empty. train_end={train_end} "
            f"data range={city_model_df['ds'].min()}..{city_model_df['ds'].max()}"
        )

    if require_test and test_city.empty:
        raise ValueError(
            f"Invalid backtest split around {train_end.date()}. "
            f"train={len(train_city)} test={len(test_city)}"
        )

    print("Train range:", train_city["ds"].min().date(), "→", train_city["ds"].max().date())
    if not test_city.empty:
        print("Test  range:", test_city["ds"].min().date(), "→", test_city["ds"].max().date())
    else:
        print("Test  range: (empty)")

    print("train_city y min/mean/max:", train_city["y"].min(), train_city["y"].mean(), train_city["y"].max())
    if not test_city.empty:
        print("test_city  y min/mean/max:", test_city["y"].min(), test_city["y"].mean(), test_city["y"].max())

    test_len = int(len(test_city))

    # Sanity checks: only apply reconstruction equality in backtest mode
    if require_test:
        assert train_city["ds"].max() <= train_end
        assert test_city["ds"].min() > train_end

        recon = pd.concat([train_city, test_city]).sort_values("ds").reset_index(drop=True)
        orig = city_model_df[["ds", "y"]].sort_values("ds").reset_index(drop=True)
        assert len(recon) == len(orig)
        assert recon["ds"].equals(orig["ds"])
        assert np.allclose(recon["y"].to_numpy(), orig["y"].to_numpy())

    return city_model_df, train_city, test_city, test_len
