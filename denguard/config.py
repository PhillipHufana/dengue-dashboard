from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class Config:
    # Forecasting horizons and dates
    # forecast_horizon_weeks: int
    train_end_date: str
    recent_weight_start: str
    calibration_threshold: int

    # IO paths
    incoming_folder: str
    master_data_csv: str
    raw_xlsx: str
    canon_csv: str
    out_dir: str

    # Modeling knobs
    incoming_mode: str = "incremental"  # "incremental" or "full_refresh"
    forecast_weeks_override: Optional[int] = None  # None => len(test)

    @property
    def out(self) -> Path:
        p = Path(self.out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

DEFAULT_CFG = Config(
    # forecast_horizon_weeks=52,
    train_end_date="2022-12-26",
    recent_weight_start="2022-01-01",
    calibration_threshold=200,
    incoming_folder=r"C:\Users\Phillip\Downloads\comsci\thesis\dengue-dashboard\dengue_incoming",
    master_data_csv=r"intermediate/dengue_master_cleaned.csv",
    raw_xlsx=r"C:\Users\Phillip\Downloads\dengue2025-2017.xlsx",
    canon_csv=r"C:\Users\Phillip\Downloads\canonical_barangays.csv",
    out_dir="intermediate",
    forecast_weeks_override=None,
    incoming_mode="incremental",
)
