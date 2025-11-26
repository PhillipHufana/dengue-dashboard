from __future__ import annotations
import pandas as pd
from typing import Dict

def standardize_barangays(df: pd.DataFrame) -> pd.DataFrame:
    print("\n== STEP 2: Standardize barangay names ==")

    df = df.copy()

    mapping: Dict[str, str] = {
        # Fix accented canonical mismatches
        "catalunan pequeno": "catalunan pequeño",
        "catalunan pequeã±o": "catalunan pequeño",

        # Canonical barangays that require parentheses
        "alejandra navarro": "alejandra navarro (lasang)",
        "centro": "centro (san juan)",
        "fatima": "fatima (benowang)",
        "san isidro": "san isidro (licanan)",
        "suawan": "suawan (tuli)",

        # Canonical barangays requiring higher-level mapping
        "dalag lumot": "dalag",
        "mati crossing": "matina crossing",
        "puan": "talomo",

        # FIX #1 — KAP TOMAS MONTEVERDE
        "kap tomas monteverde sr.": "kap. tomas monteverde, sr.",
        "kap tomas monteverde, sr.": "kap. tomas monteverde, sr.",
        "kap. tomas monteverde sr.": "kap. tomas monteverde, sr.",

        # FIX #2 — LEON GARCIA
        "leon garcia, sr.": "leon garcia sr.",
        "leon garcia sr.": "leon garcia sr.",

        # FIX #3 — LANANG → ALFONSO ANGLIONGTO SR.
        "lana": "alfonso angliongto sr.",
        "lanang": "alfonso angliongto sr.",
        "lanang (alfonso angliongto sr)": "alfonso angliongto sr.",
        "lanang (alfonso angliongto sr.)": "alfonso angliongto sr.",

        # VICENTE HIZON variations
        "vicente hizon": "vicente hizon sr.",
        "vicente hizon sr": "vicente hizon sr.",
        "vicente hizon sr. sr.": "vicente hizon sr.",

        # Gov Aquino standardization
        "gov. wilfredo aquino": "wilfredo aquino",
    }


    df["Barangay_standardized"] = (
        df["Barangay_clean"]
        # remove (Pob.), (Pob), (pob.), (pob)
        .str.replace(r"\s*\(pob\.?\)", "", regex=True)
        # remove parentheses around canon-mapped names like (Lasang)
        .str.replace(r"\s*\((.*?)\)", r"", regex=True)
        .str.strip()
        .str.lower()
        .replace(mapping)
    )

    df["Barangay_standardized"] = df["Barangay_standardized"].replace(
        ["nan", "", "none", "<na>", "unknown"], pd.NA
    )

    df = df.dropna(subset=["Barangay_standardized"])
    return df
