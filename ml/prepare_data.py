"""Clean the raw listings file and write data/housing_clean.csv.

Run from the project folder:

    python -m ml.prepare_data

The raw file is the training split of the MachineHack "House Price Prediction
Challenge" (29,451 Indian property listings). This script fixes its known
problems and removes rows that cannot be real listings.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from hvv import paths

# Limits used to drop impossible rows (typing errors in the source listings).
MIN_AREA, MAX_AREA = 200, 10_000            # square feet
MIN_PPSF, MAX_PPSF = 1_200, 60_000          # rupees per square foot
MAX_BHK = 8

# In the raw file these "cities" are Mumbai Metropolitan Region localities
# (Thane West, Mulund, Kharghar, ...) filed under a wrong city name.
CITY_FIXES = {"Lalitpur": "Mumbai", "Maharashtra": "Mumbai"}


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report = {"raw_rows": int(len(raw))}

    df = raw.rename(
        columns={
            "TARGET(PRICE_IN_LACS)": "price_lakh",
            "BHK_NO.": "bhk",
            "SQUARE_FT": "area_sqft",
            "UNDER_CONSTRUCTION": "under_construction",
            "RERA": "rera",
            "RESALE": "resale",
            "POSTED_BY": "posted_by",
            # The raw file has these two headers the wrong way round.
            "LONGITUDE": "lat",
            "LATITUDE": "lon",
        }
    )

    # "Locality,City" -> two columns.
    parts = df["ADDRESS"].str.rsplit(",", n=1, expand=True)
    df["locality"] = parts[0].str.strip()
    df["city"] = parts[1].fillna(parts[0]).str.strip().replace(CITY_FIXES)
    no_locality = parts[1].isna() | (df["locality"] == "") | (df["locality"] == df["city"])
    df.loc[no_locality, "locality"] = "Other"

    df["price"] = (df["price_lakh"] * 100_000).round().astype("int64")
    df["area_sqft"] = df["area_sqft"].round(1)

    before = len(df)
    df = df.drop_duplicates(
        subset=["city", "locality", "area_sqft", "bhk", "under_construction",
                "rera", "resale", "posted_by", "price"]
    )
    report["duplicates_removed"] = int(before - len(df))

    ppsf = df["price"] / df["area_sqft"]
    keep = (
        df["area_sqft"].between(MIN_AREA, MAX_AREA)
        & ppsf.between(MIN_PPSF, MAX_PPSF)
        & (df["bhk"] <= MAX_BHK)
    )
    report["outliers_removed"] = int((~keep).sum())
    df = df[keep]

    # Coordinates outside India are geocoding failures; blank them out.
    in_india = df["lat"].between(6, 37) & df["lon"].between(68, 98)
    report["bad_coordinates_blanked"] = int((~in_india).sum())
    df.loc[~in_india, ["lat", "lon"]] = np.nan

    df = df[
        ["city", "locality", "area_sqft", "bhk", "under_construction", "rera",
         "resale", "posted_by", "lat", "lon", "price"]
    ].sort_values(["city", "locality", "area_sqft", "price"]).reset_index(drop=True)

    report["clean_rows"] = int(len(df))
    report["cities"] = int(df["city"].nunique())
    report["localities"] = int((df["city"] + "|" + df["locality"]).nunique())
    report["limits"] = {
        "area_sqft": [MIN_AREA, MAX_AREA],
        "price_per_sqft": [MIN_PPSF, MAX_PPSF],
        "max_bhk": MAX_BHK,
    }
    return df, report


def main() -> None:
    raw = pd.read_csv(paths.RAW_DATA)
    df, report = clean(raw)
    df.to_csv(paths.CLEAN_DATA, index=False)
    (paths.DATA_DIR / "cleaning_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"Wrote {paths.CLEAN_DATA}")


if __name__ == "__main__":
    main()
