from __future__ import annotations

import glob
import os
from typing import List
import pandas as pd

def load_new_raw_files(incoming_folder: str) -> pd.DataFrame:
    """Load all .xlsx in incoming folder. Add __source_file column."""
    files = glob.glob(os.path.join(incoming_folder, "*.xlsx"))
    if not files:
        print("✅ No new files found in incoming folder.")
        return pd.DataFrame()

    dfs: List[pd.DataFrame] = []
    for f in files:
        try:
            temp = pd.read_excel(f)
            temp["__source_file"] = os.path.basename(f)
            dfs.append(temp)
            print(f"✅ Loaded new file: {f}")
        except Exception as e:
            print(f"⚠️ Failed to load {f}: {e}")

    if not dfs:
        return pd.DataFrame()

    new_data = pd.concat(dfs, ignore_index=True)
    print(f"✅ Total new rows loaded: {len(new_data):,}")
    return new_data
