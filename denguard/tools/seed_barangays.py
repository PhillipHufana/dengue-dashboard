# file: tools/seed_barangays.py
from __future__ import annotations
import os
import pandas as pd
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
API_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
)
assert API_KEY, "Missing Supabase key (SERVICE_ROLE_KEY / SERVICE_KEY / ANON_KEY)."

OUT_DIR = Path("intermediate")  # cfg.out
CSV = OUT_DIR / "weekly_cases_all_barangays.csv"

def headers():
    return {
        "apikey": API_KEY,
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

def main():
    df = pd.read_csv(CSV)
    names = (
        df["Barangay_key"]
        .astype(str)
        .str.strip()
        .str.lower()
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    rows = [{"name": n} for n in names]  # server generates UUID id

    # Use PostgREST upsert with conflict target if you have a unique index on lower(name)
    params = {"on_conflict": "name_lower"}  # see SQL below
    url = f"{SUPABASE_URL}/rest/v1/barangays"

    # chunk to avoid big payloads
    BATCH = 1000
    total = 0
    with requests.Session() as s:
        for i in range(0, len(rows), BATCH):
            chunk = rows[i : i + BATCH]
            r = s.post(url, headers=headers(), params=params, json=chunk, timeout=20)
            r.raise_for_status()
            total += len(chunk)
    print(f"✅ Seeded/updated {total} barangays")

if __name__ == "__main__":
    main()
