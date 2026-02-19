import csv
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

from api.supabase_client import get_supabase  # uses your get_supabase()

def normalize_name(s: str) -> str:
    x = (s or "").lower().strip()
    x = unicodedata.normalize("NFD", x)
    x = "".join(ch for ch in x if unicodedata.category(ch) != "Mn")
    x = re.sub(r"\(.*?\)", "", x)          # drop parentheticals
    x = x.replace("-", " ")
    x = re.sub(r"[^a-z0-9 ]", "", x)       # drop punctuation
    x = re.sub(r"\s+", " ", x).strip()
    return x

SRC = Path("C:\\Users\\Phillip\\Downloads\\comsci\\thesis\\dengue-dashboard\\data\\population.csv")  # set path
AS_OF = date(2024, 7, 1)      # change if you want another date

BATCH = 200

def main():
    sb = get_supabase()

    rows = []
    with SRC.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            raw = r.get("Name") or ""
            pop_raw = r.get("Population")
            if not raw or pop_raw is None or str(pop_raw).strip() == "":
                continue

            name = normalize_name(raw)
            pop = int(str(pop_raw).replace(",", "").strip())

            rows.append({
                "name": name,
                "as_of_date": AS_OF.isoformat(),
                "population": pop,
            })

    # sanity: count and sample
    print("rows:", len(rows))
    print("sample:", rows[:5])

    # upsert in one batch (or chunk)
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i+BATCH]
        sb.table("barangay_population").upsert(
            chunk,
            on_conflict="name,as_of_date",
        ).execute()

    # validate coverage: which normalized names don’t exist in barangays?
    missing = []
    for r in rows:
        nm = r["name"]
        hit = sb.table("barangays").select("name").eq("name", nm).limit(1).execute().data
        if not hit:
            missing.append(nm)

    if missing:
        print("WARNING: population names not found in barangays (first 30):", missing[:30])
    else:
        print("All population rows matched barangays.name")

if __name__ == "__main__":
    main()
