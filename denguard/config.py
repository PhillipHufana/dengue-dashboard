# denguard/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal

RunKind = Literal["backtest", "production"]

@dataclass(frozen=True)
class Config:
    # --- run metadata ---
    run_id: Optional[str] = None
    run_started_at_utc: Optional[str] = None

    # --- NEW (G0.3): run kind ---
    run_kind: RunKind = "backtest"  # "backtest" or "production"

    # Config fields
    policy_local_perf_csv: str = ""   # pinned backtest policy
    production_enable_local_overrides: bool = True


    # --- Backtest cutoff (thesis validation) ---
    backtest_end_date: str = "2022-12-26"  # replaces old fixed train_end_date conceptually

    # --- Production horizon ---
    production_horizon_weeks: int = 52

    # --- Production fallback model if no test exists ---
    production_city_model: Literal["prophet", "arima"] = "prophet"

    # --- Rolling weighting window for top-down disaggregation ---
    disagg_weight_weeks: int = 52
    disagg_scheme_production: Literal["static", "rolling", "seasonal", "hybrid"] = "rolling"
    disagg_ablation_schemes: tuple[str, ...] = ("static", "rolling", "seasonal")
    production_use_latest_disagg_ablation: bool = True
    disagg_hybrid_lambda: float = 0.5
    disagg_alpha_smooth: float = 1.0
    recent_weight_start: str = "2022-01-01"  # legacy field retained for backward compatibility
    calibration_threshold: int = 200

    # --- Choice A: local only if it beats disagg on test (sMAPE) ---
    local_vs_disagg_smape_margin: float = 0.03

    # --- Local model eligibility (data sufficiency) ---
    local_min_train_weeks: int = 104          # 2 yearly cycles (defensible for yearly seasonality)
    local_min_nonzero_weeks: int = 20         # avoids “mostly-zero” series
    local_min_total_cases: int = 50           # prevents fitting on near-empty signals

    # IO paths
    incoming_folder: str = ""
    master_data_csv: str = ""
    raw_xlsx: str = ""
    canon_csv: str = ""
    out_dir: str = ""

    # Pipeline mode (your existing ingestion mode)
    incoming_mode: str = "incremental"  # "incremental" or "full_refresh"

    # Horizon override (still useful, especially for backtest)
    forecast_weeks_override: Optional[int] = None  # None => len(test) (backtest), production uses production_horizon_weeks

    @property
    def out(self) -> Path:
        p = Path(self.out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


DEFAULT_CFG = Config(
    run_kind="backtest",
    backtest_end_date="2022-12-26",
    production_horizon_weeks=52,
    production_city_model="prophet",
    disagg_weight_weeks=52,
    disagg_scheme_production="rolling",
    disagg_ablation_schemes=("static", "rolling", "seasonal"),
    production_use_latest_disagg_ablation=True,
    disagg_hybrid_lambda=0.5,
    disagg_alpha_smooth=1.0,
    recent_weight_start="2022-01-01",
    calibration_threshold=200,
    incoming_folder=r"C:\Users\Phillip\Downloads\comsci\thesis\dengue-dashboard\dengue_incoming",
    master_data_csv=r"intermediate/dengue_master_cleaned.csv",
    raw_xlsx=r"C:\Users\Phillip\Downloads\dengue2025-2017.xlsx",
    canon_csv=r"C:\Users\Phillip\Downloads\canonical_barangays.csv",
    out_dir="intermediate",
    forecast_weeks_override=None,
    incoming_mode="incremental",
    policy_local_perf_csv=r"policies/local_model_performance_backtest_2022-12-26_3b3037b5.csv",
    production_enable_local_overrides=True,
    local_vs_disagg_smape_margin=0.03,
)
