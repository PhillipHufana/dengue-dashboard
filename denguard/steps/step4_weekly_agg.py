from __future__ import annotations
import pandas as pd
from denguard.config import Config
from denguard.keys import make_barangay_db_key

def weekly_aggregation(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    STEP 4 — Convert daily onset cases into weekly Barangay → Cases.
    """
    print("\n== STEP 4: Weekly aggregation ==")

    df = df.copy()
    df["date_onset"] = pd.to_datetime(df["DOnset"], errors="coerce")
    df = df.dropna(subset=["date_onset"])
    df = df[df["date_onset"] >= pd.Timestamp("2017-01-01")]

    # Compute week start
    df["WeekStart"] = df["date_onset"] - pd.to_timedelta(df["date_onset"].dt.weekday, unit="d")
    df["WeekStart"] = df["WeekStart"].dt.floor("D")
    df = df.dropna(subset=["Barangay_key"])

    weekly = (
        df.groupby(["Barangay_key", "WeekStart"])
        .size()
        .reset_index(name="Cases")
    )

    start_date = df["WeekStart"].min()
    end_date = weekly["WeekStart"].max()

    weeks = pd.date_range(start_date, end_date, freq="W-MON")
    canonical = pd.read_csv(cfg.canon_csv)
    # build keys in the same style as your DB name keys
    canonical_keys = canonical["canonical_name"].map(make_barangay_db_key).dropna().unique()
    barangays = canonical_keys

    extra = set(weekly["Barangay_key"]) - set(barangays)
    if extra:
        raise ValueError(f"Barangay keys not in canonical list: {sorted(extra)}")


    template = pd.MultiIndex.from_product(
        [barangays, weeks], names=["Barangay_key", "WeekStart"]
    ).to_frame(index=False)

    # After filtering + dropping NA barangay_key:
    n_case_rows = len(df)

    # weekly counts should sum exactly to number of case rows
    sum_weekly = int(weekly["Cases"].sum())

    print("Case rows after onset+date range+barangay_key filters:", n_case_rows)
    print("Sum of weekly grouped Cases:", sum_weekly)

    if sum_weekly != n_case_rows:
        raise RuntimeError(f"Weekly sum mismatch: grouped={sum_weekly} vs rows={n_case_rows}")

    weekly_full = (
        template.merge(weekly, on=["Barangay_key", "WeekStart"], how="left")
        .fillna({"Cases": 0})
        .sort_values(["Barangay_key", "WeekStart"])
    )

    # ✅ G0.4: tag every row with run_id
    weekly_full["run_id"] = cfg.run_id


    # Ensure all barangays have same week count
    week_counts = weekly_full.groupby("Barangay_key")["WeekStart"].count()
    assert week_counts.nunique() == 1, "❌ Inconsistent week counts per barangay!"

    ws = pd.to_datetime(weekly["WeekStart"]).sort_values()
    print("Weekly dayofweek unique:", ws.dt.dayofweek.unique())  # should be [0]

    print(f"✅ All barangays have {week_counts.iloc[0]} weeks of data.")

    weekly_full = weekly_full[["run_id", "Barangay_key", "WeekStart", "Cases"]]

    weekly_full.to_csv(
        cfg.out / "weekly_cases_all_barangays.csv",
        index=False,
        encoding="utf-8-sig"
    )
    print(f"✅ Saved full weekly dataset ({len(weekly_full):,} rows)")

    print("Weekly template start:", weeks.min(), "end:", weeks.max(), "n_weeks:", len(weeks))
    print("Canonical barangays:", len(barangays))
    print("weekly_full shape:", weekly_full.shape)
    print("Expected rows:", len(barangays) * len(weeks))

    return weekly_full
