"""The price model: how it is built, trained, saved and loaded.

Locality and city are turned into numbers with target encoding, each locality
also brings its map position, and a gradient-boosted tree ensemble
(scikit-learn's HistGradientBoostingRegressor) predicts the price on a log
scale. The trees are constrained so that, with everything else equal, a larger
home is never estimated cheaper than a smaller one.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import TargetEncoder

from . import paths

# What the caller must provide for every home.
INPUT_COLUMNS = ["city", "locality", "area_sqft", "bhk",
                 "under_construction", "rera", "resale"]
CATEGORY_COLUMNS = ["city", "loc"]
NUMERIC_COLUMNS = ["area_sqft", "bhk", "under_construction", "rera", "resale",
                   "lat", "lon"]

OTHER_LOCALITY = "Other"
MIN_LOCALITY_COUNT = 5      # a locality needs this many listings to stand alone
INTERVAL_COVERAGE = 0.80    # the low-high range should contain 80% of real prices


def default_regressor() -> HistGradientBoostingRegressor:
    # One entry per model input, in order: city, locality, then NUMERIC_COLUMNS.
    # 1 means "the prediction may only rise as this input rises" (the area).
    monotonic = [0, 0] + [1 if col == "area_sqft" else 0 for col in NUMERIC_COLUMNS]
    return HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_iter=800,
        early_stopping=False,
        monotonic_cst=monotonic,
        random_state=0,
    )


class PriceRegressor(RegressorMixin, BaseEstimator):
    """Predicts a home's price in rupees from the INPUT_COLUMNS.

    ``fit`` also accepts ``lat`` and ``lon`` columns; it remembers where each
    locality is so ``predict`` does not need coordinates.
    """

    def __init__(self, regressor=None, per_sqft=False,
                 min_locality_count=MIN_LOCALITY_COUNT):
        self.regressor = regressor
        self.per_sqft = per_sqft            # learn price per sq ft instead of price
        self.min_locality_count = min_locality_count

    # -- feature building -------------------------------------------------
    @staticmethod
    def _key(X: pd.DataFrame) -> pd.Series:
        return X["city"].astype(str) + "|" + X["locality"].astype(str)

    def _design(self, X: pd.DataFrame) -> pd.DataFrame:
        key = self._key(X)
        known = key.isin(self.known_localities_)
        out = pd.DataFrame(index=X.index)
        out["city"] = X["city"].astype(str)
        # Rare or unseen localities share one "Other" bucket per city.
        out["loc"] = key.where(known, out["city"] + "|" + OTHER_LOCALITY)
        for col in ("area_sqft", "bhk", "under_construction", "rera", "resale"):
            out[col] = pd.to_numeric(X[col]).astype(float)
        for i, col in enumerate(("lat", "lon")):
            by_locality = key.map(lambda k: self.locality_geo_.get(k, (np.nan, np.nan))[i])
            by_city = out["city"].map(lambda c: self.city_geo_.get(c, (np.nan, np.nan))[i])
            out[col] = by_locality.where(known, by_city).astype(float)
        return out

    # -- scikit-learn API -------------------------------------------------
    def fit(self, X: pd.DataFrame, y):
        X = X.reset_index(drop=True)
        price = np.asarray(y, dtype=float)
        key = self._key(X)

        counts = key.value_counts()
        self.known_localities_ = set(counts[counts >= self.min_locality_count].index)

        if {"lat", "lon"}.issubset(X.columns):
            geo = X[["lat", "lon"]].astype(float)
            loc_geo = geo.groupby(key).median()
            city_geo = geo.groupby(X["city"].astype(str)).median()
            self.locality_geo_ = {k: (r.lat, r.lon) for k, r in loc_geo.iterrows()}
            self.city_geo_ = {k: (r.lat, r.lon) for k, r in city_geo.iterrows()}
        else:
            self.locality_geo_, self.city_geo_ = {}, {}

        design = self._design(X)
        area = design["area_sqft"].to_numpy()

        # City and locality become numbers: the typical (log) price per sq ft
        # there. fit_transform cross-fits, so a listing never sees its own price.
        self.encoder_ = TargetEncoder(target_type="continuous", random_state=0)
        encoded = self.encoder_.fit_transform(design[CATEGORY_COLUMNS], np.log(price / area))

        self.regressor_ = default_regressor() if self.regressor is None else clone(self.regressor)
        target = price / area if self.per_sqft else price
        self.regressor_.fit(self._matrix(encoded, design), np.log(target))
        return self

    @staticmethod
    def _matrix(encoded: np.ndarray, design: pd.DataFrame) -> np.ndarray:
        return np.column_stack([encoded, design[NUMERIC_COLUMNS].to_numpy()])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        design = self._design(X)
        encoded = self.encoder_.transform(design[CATEGORY_COLUMNS])
        predicted = np.exp(self.regressor_.predict(self._matrix(encoded, design)))
        return predicted * design["area_sqft"].to_numpy() if self.per_sqft else predicted

    def is_known_locality(self, city: str, locality: str) -> bool:
        return f"{city}|{locality}" in self.known_localities_


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_clean_data() -> pd.DataFrame:
    return pd.read_csv(paths.CLEAN_DATA)


def build_catalog(df: pd.DataFrame, min_city_listings: int = 20) -> dict:
    """Cities and localities the app offers, with a few facts about each."""
    df = df.assign(ppsf=df["price"] / df["area_sqft"])
    cities = {}
    for city, g in df.groupby("city"):
        if len(g) < min_city_listings:
            continue
        loc = g.groupby("locality").agg(n=("price", "size"), ppsf=("ppsf", "median"))
        loc = loc[(loc["n"] >= MIN_LOCALITY_COUNT) & (loc.index != OTHER_LOCALITY)]
        cities[city] = {
            "listings": int(len(g)),
            "median_ppsf": round(float(g["ppsf"].median())),
            "median_price": round(float(g["price"].median())),
            "median_area": round(float(g["area_sqft"].median())),
            "localities": {
                name: {"listings": int(r.n), "median_ppsf": round(float(r.ppsf))}
                for name, r in loc.sort_index().iterrows()
            },
        }
    return {
        "total_listings": int(len(df)),
        "total_cities": int(df["city"].nunique()),
        "cities": cities,
    }


# ---------------------------------------------------------------------------
# Saving and loading
# ---------------------------------------------------------------------------
def save_bundle(model: PriceRegressor, interval: dict, n_rows: int) -> None:
    paths.MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "interval": interval,
            "sklearn_version": sklearn.__version__,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_rows": n_rows,
        },
        paths.MODEL_FILE,
        compress=3,
    )


def train_final_model(df: pd.DataFrame | None = None) -> PriceRegressor:
    """Fit the chosen model on every clean listing."""
    if df is None:
        df = load_clean_data()
    return PriceRegressor().fit(df[INPUT_COLUMNS + ["lat", "lon"]], df["price"])


def _stored_interval() -> dict:
    """Low/high range factors measured by ml/train.py (they depend on the data,
    not on the scikit-learn version, so they survive a quick retrain)."""
    try:
        return json.loads(paths.METRICS_FILE.read_text())["interval"]
    except Exception:
        return {"listed": {"low": -0.30, "high": 0.30},
                "other": {"low": -0.45, "high": 0.45},
                "coverage": INTERVAL_COVERAGE}


def load_bundle(allow_retrain: bool = True) -> dict:
    """Load the saved model.

    A model file only loads reliably with the scikit-learn version that wrote
    it. If this machine has a different version (or the file is missing), the
    model is retrained from data/housing_clean.csv, which takes a few seconds.
    """
    try:
        bundle = joblib.load(paths.MODEL_FILE)
        if bundle.get("sklearn_version") == sklearn.__version__:
            return bundle
    except Exception:
        pass
    if not allow_retrain:
        raise RuntimeError("The saved model does not match this scikit-learn version.")
    df = load_clean_data()
    model = train_final_model(df)
    interval = _stored_interval()
    try:
        save_bundle(model, interval, len(df))
    except OSError:
        pass  # read-only folder: keep the model in memory only
    return {"model": model, "interval": interval,
            "sklearn_version": sklearn.__version__, "n_rows": len(df)}
