# file: denguard/horizon.py
from __future__ import annotations

from denguard.config import Config


def resolve_horizon(cfg: Config, test_len: int) -> int:
    """
    Decide the forecast horizon (in weeks) for the pipeline.

    Rules:
      - If cfg.forecast_weeks_override is not None:
            use that value.
      - Otherwise:
            use test_len (length of the test set).

    This lets you:
      - In *testing/thesis* mode:
            cfg.forecast_weeks_override = None
            -> horizon = len(test)
      - In *dashboard/production* mode:
            cfg.forecast_weeks_override = N (e.g., 52)
            -> horizon = N, regardless of test length.
    """
    if cfg.forecast_weeks_override is not None:
        horizon = int(cfg.forecast_weeks_override)
    else:
        horizon = int(test_len)

    if horizon <= 0:
        raise ValueError(f"Resolved forecast horizon must be positive, got {horizon}.")

    return horizon
