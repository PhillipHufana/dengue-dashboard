from __future__ import annotations
from typing import Tuple, List
import glob
import hashlib
import os
from pathlib import Path
import pandas as pd

def _file_md5(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()

def load_new_raw_files(incoming_folder: str, processed_registry_csv: str) -> Tuple[pd.DataFrame, List[str]]:
    """
    Load all .xlsx in incoming folder, skipping files already processed (by md5).
    Adds __source_file, __file_md5, __file_mtime_utc columns.
    """
    files = glob.glob(os.path.join(incoming_folder, "*.xlsx")) + glob.glob(os.path.join(incoming_folder, "*.csv"))
    if not files:
        print("✅ No new files found in incoming folder.")
        return pd.DataFrame(), []

    registry_path = Path(processed_registry_csv)
    if registry_path.exists():
        reg = pd.read_csv(registry_path, dtype={"file_md5": "string"})
        seen = set(reg["file_md5"].dropna().astype(str))
    else:
        reg = pd.DataFrame(columns=["file_md5", "source_file", "processed_at_utc"])
        seen = set()

    dfs: List[pd.DataFrame] = []
    loaded_files: List[str] = []
    new_rows_registry = []

    for f in files:
        try:
            md5 = _file_md5(f)
            if md5 in seen:
                print(f"↩️ Skipped already-processed file: {os.path.basename(f)}")
                continue

            if f.lower().endswith(".xlsx"):
                temp = pd.read_excel(f, dtype={"CASE ID": "string"})
            else:
                temp = pd.read_csv(f, dtype={"CASE ID": "string"}, low_memory=False)

            temp["__source_row"] = range(len(temp))
            temp["__source_file"] = os.path.basename(f)
            temp["__file_md5"] = md5
            temp["__file_mtime_utc"] = pd.to_datetime(os.path.getmtime(f), unit="s", utc=True)

            dfs.append(temp)
            loaded_files.append(os.path.basename(f))
            new_rows_registry.append({
                "file_md5": md5,
                "source_file": os.path.basename(f),
                "processed_at_utc": pd.Timestamp.utcnow()
            })
            print(f"✅ Loaded new file: {f}")

        except Exception as e:
            print(f"⚠️ Failed to load {f}: {e}")

    # update registry
    if new_rows_registry:
        reg = pd.concat([reg, pd.DataFrame(new_rows_registry)], ignore_index=True)
        reg.to_csv(registry_path, index=False)

    if not dfs:
        return pd.DataFrame(), []

    new_data = pd.concat(dfs, ignore_index=True)
    print(f"✅ Total new rows loaded: {len(new_data):,}")
    return new_data, loaded_files
