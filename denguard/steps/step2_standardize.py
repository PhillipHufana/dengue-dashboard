from __future__ import annotations

import re
import unicodedata
import pandas as pd
from typing import Dict
from denguard.keys import make_barangay_db_key

def standardize_barangays(df: pd.DataFrame) -> pd.DataFrame:
    print("\n== STEP 2: Standardize barangay names ==")
    df = df.copy()

    if "Barangay_clean" not in df.columns:
        raise KeyError("Missing column 'Barangay_clean' (run Step 1 first)")

    # Create DB-join key
    df["Barangay_key"] = df["Barangay_clean"].map(make_barangay_db_key)

    # Apply true aliases that should map to DB keys (NOT display names)
    alias_map: Dict[str, str] = {
        # Higher-level mapping / known aliasing
        "dalag lumot": "dalag",
        "mati crossing": "matina crossing",
        "puan": "talomo",

        # Lanang variants -> DB key
        "lana": "alfonso angliongto sr",
        "lanang": "alfonso angliongto sr",

        # Vicente Hizon variants
        "vicente hizon": "vicente hizon sr",
        "vicente hizon sr sr": "vicente hizon sr",

        # Gov Aquino variants
        "gov wilfredo aquino": "wilfredo aquino",

        # FIX the 2 bad rows:
        "catalunan pequea o": "catalunan pequeno",
    }

    df["Barangay_key"] = df["Barangay_key"].replace(alias_map)
    # normalize again so alias outputs are guaranteed DB-key format
    df["Barangay_key"] = df["Barangay_key"].map(make_barangay_db_key)
    # Normalize empties
    df["Barangay_key"] = df["Barangay_key"].replace(
        ["", "nan", "na", "none", "<na>", "unknown"], pd.NA
    )

    # Keep a display label if you want (optional)
    df["Barangay_display"] = df["Barangay_clean"]

    # DO NOT drop NA keys here; validation step should log them
    return df
