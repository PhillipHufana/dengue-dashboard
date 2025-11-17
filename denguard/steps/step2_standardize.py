from __future__ import annotations
from typing import Dict
import pandas as pd

def standardize_barangays(df: pd.DataFrame) -> pd.DataFrame:
    print("\n== STEP 2: Standardize barangay names ==")
    mapping: Dict[str, str] = {
        "catalunan pequeã±o": "catalunan pequeño",
        "leon garcia, sr.": "leon garcia sr.",
        "kap tomas monteverde sr.": "kap. tomas monteverde, sr.",
        "kap. tomas monteverde sr.": "kap. tomas monteverde, sr.",
        "kap tomas monteverde, sr.": "kap. tomas monteverde, sr.",
        "alejandra navarro": "alejandra navarro (lasang)",
        "centro": "centro (san juan)",
        "fatima": "fatima (benowang)",
        "san isidro": "san isidro (licanan)",
        "suawan": "suawan (tuli)",
        "dalag lumot": "dalag",
        "lana": "alfonso angliongto sr.",
        "lanang": "alfonso angliongto sr.",
        "mati crossing": "matina crossing",
        "puan": "talomo",
        "vicente hizon": "vicente hizon sr.",
        "vicente hizon sr": "vicente hizon sr.",
        "vicente hizon sr. sr.": "vicente hizon sr.",
        "gov. wilfredo aquino": "wilfredo aquino",
    }

    df = df.copy()
    df["Barangay_standardized"] = df["Barangay_clean"].replace(mapping).str.strip().str.lower()
    df["Barangay_standardized"] = df["Barangay_standardized"].replace(
        ["nan", "none", "", "unknown", "<na>", "na"], pd.NA
    )
    df = df.dropna(subset=["Barangay_standardized"])
    return df