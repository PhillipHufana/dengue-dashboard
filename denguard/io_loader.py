from __future__ import annotations

from typing import Any, List, Tuple
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


def load_new_raw_files(
    incoming_folder: str,
    processed_registry_csv: str,
) -> Tuple[pd.DataFrame, List[str], List[dict[str, Any]]]:
    """
    Load all .xlsx/.csv in the incoming folder, skipping files already processed (by md5).
    Adds __source_file, __file_md5, __file_mtime_utc columns.

    Returns:
      - concatenated dataframe of new rows
      - loaded file basenames
      - pending registry rows to be committed only after the pipeline succeeds
    """
    files = glob.glob(os.path.join(incoming_folder, "*.xlsx")) + glob.glob(os.path.join(incoming_folder, "*.csv"))
    if not files:
        print("No new files found in incoming folder.")
        return pd.DataFrame(), [], []

    registry_path = Path(processed_registry_csv)
    if registry_path.exists():
        reg = pd.read_csv(registry_path, dtype={"file_md5": "string"})
        seen = set(reg["file_md5"].dropna().astype(str))
    else:
        seen = set()

    dfs: List[pd.DataFrame] = []
    loaded_files: List[str] = []
    pending_registry_rows: List[dict[str, Any]] = []

    for f in files:
        try:
            md5 = _file_md5(f)
            if md5 in seen:
                print(f"Skipped already-processed file: {os.path.basename(f)}")
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
            pending_registry_rows.append(
                {
                    "file_md5": md5,
                    "source_file": os.path.basename(f),
                    "processed_at_utc": pd.Timestamp.utcnow(),
                }
            )
            print(f"Loaded new file: {f}")
        except Exception as e:
            print(f"Failed to load {f}: {e}")

    if not dfs:
        return pd.DataFrame(), [], pending_registry_rows

    new_data = pd.concat(dfs, ignore_index=True)
    print(f"Total new rows loaded: {len(new_data):,}")
    return new_data, loaded_files, pending_registry_rows


def finalize_processed_registry(processed_registry_csv: str, pending_rows: List[dict[str, Any]]) -> None:
    """
    Persist file fingerprints only after the local pipeline run has completed successfully.
    """
    if not pending_rows:
        return

    registry_path = Path(processed_registry_csv)
    if registry_path.exists():
        reg = pd.read_csv(registry_path, dtype={"file_md5": "string"})
    else:
        reg = pd.DataFrame(columns=["file_md5", "source_file", "processed_at_utc"])

    pending = pd.DataFrame(pending_rows)
    reg = pd.concat([reg, pending], ignore_index=True)
    reg["file_md5"] = reg["file_md5"].astype("string")
    reg = reg.drop_duplicates(subset=["file_md5"], keep="last")
    reg.to_csv(registry_path, index=False)
