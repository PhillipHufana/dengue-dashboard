from __future__ import annotations

from typing import Optional, Sequence, Dict, List
import math

PCTS = {"low": 0.75, "medium": 0.90, "high": 0.975}


def _safe_incidence(cases: float, population: Optional[int]) -> Optional[float]:
    if not population or population <= 0:
        return None
    return (float(cases) / float(population)) * 100000.0


def _percentile(sorted_vals: Sequence[float], p: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_vals[0])
    idx = (n - 1) * p
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(sorted_vals[lo])
    w = idx - lo
    return float(sorted_vals[lo]) * (1 - w) + float(sorted_vals[hi]) * w


def rolling_window_sums(history_cases: Sequence[int], window_weeks: int) -> List[float]:
    """
    Converts weekly history into rolling window sums.

    Example:
      history=[1,2,3,4], window=2 => [1+2, 2+3, 3+4] => [3,5,7]
    """
    w = max(int(window_weeks or 1), 1)
    vals = [float(x or 0) for x in history_cases]
    if len(vals) < w:
        return [sum(vals)] if vals else [0.0]

    out: List[float] = []
    run_sum = sum(vals[:w])
    out.append(run_sum)
    for i in range(w, len(vals)):
        run_sum += vals[i] - vals[i - w]
        out.append(run_sum)
    return out


def risk_from_baseline_percentiles(
    forecast_cases: float,
    history_cases: Sequence[int],
    population: Optional[int] = None,
) -> Dict[str, Optional[object]]:
    hist_cases = sorted(float(x or 0) for x in history_cases)
    c75 = _percentile(hist_cases, PCTS["low"])
    c90 = _percentile(hist_cases, PCTS["medium"])
    c975 = _percentile(hist_cases, PCTS["high"])

    fc = float(forecast_cases or 0.0)

    if c75 == c90 == c975:
        if fc < 0.5:
            risk_cases = "low"
        elif fc < 2:
            risk_cases = "medium"
        elif fc <= 5:
            risk_cases = "high"
        else:
            risk_cases = "critical"
    else:
        if fc < c75:
            risk_cases = "low"
        elif fc < c90:
            risk_cases = "medium"
        elif fc < c975:
            risk_cases = "high"
        else:
            risk_cases = "critical"

    inc = _safe_incidence(fc, population)
    risk_inc = None

    if population and population > 0:
        hist_inc = sorted((_safe_incidence(float(x or 0), population) or 0.0) for x in history_cases)
        i75 = _percentile(hist_inc, PCTS["low"])
        i90 = _percentile(hist_inc, PCTS["medium"])
        i975 = _percentile(hist_inc, PCTS["high"])

        if inc is None:
            risk_inc = None
        elif i75 == i90 == i975:
            if inc == 0:
                risk_inc = "low"
            elif inc <= 2:
                risk_inc = "medium"
            elif inc <= 5:
                risk_inc = "high"
            else:
                risk_inc = "critical"
        else:
            if inc < i75:
                risk_inc = "low"
            elif inc < i90:
                risk_inc = "medium"
            elif inc < i975:
                risk_inc = "high"
            else:
                risk_inc = "critical"

    return {
        "forecast_incidence_per_100k": inc,
        "risk_level_cases": risk_cases,
        "risk_level_incidence": risk_inc,
    }


def risk_from_baseline_percentiles_windowed(
    forecast_cases_sum: float,
    history_weekly_cases: Sequence[int],
    population: Optional[int],
    window_weeks: int,
) -> Dict[str, Optional[object]]:
    """
    Correct risk calculation for a multi-week forecast sum:
      - baseline is built from rolling window sums of the SAME window size.
      - incidence is computed for that same summed period (still per 100k people).

    This fixes "3 months risk map looks wrong" because units now match.
    """
    baseline_sums = rolling_window_sums(history_weekly_cases, window_weeks=window_weeks)
    # We pass "baseline sums" as the history into the existing percentile logic.
    return risk_from_baseline_percentiles(
        forecast_cases=float(forecast_cases_sum or 0.0),
        history_cases=baseline_sums,
        population=population,
    )