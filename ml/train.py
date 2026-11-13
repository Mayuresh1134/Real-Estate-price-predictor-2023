"""Compare regression models, then train and save the best one.

Run from the project folder:

    python -m ml.train

It writes three files into models/:
    price_model.joblib   the trained model the app uses
    metrics.json         how each model scored (shown on the Insights page)
    catalog.json         the cities and localities offered in the app
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, train_test_split
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder

from hvv import modeling, paths
from hvv.modeling import INPUT_COLUMNS, PriceRegressor

SEED = 42
FIT_COLUMNS = INPUT_COLUMNS + ["lat", "lon"]


# ---------------------------------------------------------------------------
# Candidate models. Each takes the same table and returns a price in rupees.
# ---------------------------------------------------------------------------
class ClippedLinear:
    """Ordinary linear regression on the raw price (the project's old approach).
    A straight line can predict a negative price, so the result is floored."""

    def __init__(self, columns, categorical=()):
        self.columns, self.categorical = list(columns), list(categorical)

    def fit(self, X, y):
        numeric = [c for c in self.columns if c not in self.categorical]
        self.model_ = Pipeline([
            ("prep", ColumnTransformer([
                ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20),
                 self.categorical),
                ("num", "passthrough", numeric),
            ])),
            ("lin", LinearRegression()),
        ]).fit(X[self.columns], y)
        return self

    def predict(self, X):
        return np.clip(self.model_.predict(X[self.columns]), 100_000, None)


CANDIDATES = {
    "Linear regression (area, bedrooms)":
        lambda: ClippedLinear(["area_sqft", "bhk"]),
    "Linear regression (+ city, status)":
        lambda: ClippedLinear(
            ["city", "area_sqft", "bhk", "under_construction", "rera", "resale"],
            categorical=["city"]),
    "Ridge regression (per sq ft, + locality)":
        lambda: PriceRegressor(per_sqft=True, regressor=make_pipeline(
            SimpleImputer(strategy="median"), Ridge(alpha=1.0))),
    "Random forest":
        lambda: PriceRegressor(per_sqft=True, regressor=make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestRegressor(n_estimators=300, max_features=0.5,
                                  n_jobs=-1, random_state=0))),
    "Gradient boosting (chosen)":
        lambda: PriceRegressor(),
}
CHOSEN = "Gradient boosting (chosen)"
BASELINE = "Linear regression (area, bedrooms)"


def score(actual: np.ndarray, predicted: np.ndarray) -> dict:
    ape = np.abs(predicted - actual) / actual
    return {
        "r2": float(r2_score(actual, predicted)),
        "r2_log": float(r2_score(np.log(actual), np.log(predicted))),
        "mae_lakh": float(mean_absolute_error(actual, predicted) / 1e5),
        "median_error_pct": float(np.median(ape) * 100),
        "within_10_pct": float(np.mean(ape <= 0.10) * 100),
        "within_20_pct": float(np.mean(ape <= 0.20) * 100),
    }


def out_of_fold(make, X: pd.DataFrame, y: pd.Series, folds: int = 5) -> np.ndarray:
    """Predictions for every row, each made by a model that never saw that row."""
    predicted = np.empty(len(X))
    for train_idx, test_idx in KFold(folds, shuffle=True, random_state=SEED).split(X):
        model = make().fit(X.iloc[train_idx], y.iloc[train_idx])
        predicted[test_idx] = model.predict(X.iloc[test_idx])
    return predicted


def interval_from_residuals(model_for_groups: PriceRegressor, X, actual, predicted) -> dict:
    """How far real prices usually sit from the estimate, as log factors.

    Measured separately for localities the model knows by name ("listed") and
    for the per-city "Other" bucket, where estimates are less certain.
    """
    resid = np.log(actual) - np.log(predicted)
    known = np.array([model_for_groups.is_known_locality(c, l)
                      for c, l in zip(X["city"], X["locality"])])
    tail = (1 - modeling.INTERVAL_COVERAGE) / 2
    out = {"coverage": modeling.INTERVAL_COVERAGE}
    for name, mask in (("listed", known), ("other", ~known)):
        out[name] = {
            "low": float(np.quantile(resid[mask], tail)),
            "high": float(np.quantile(resid[mask], 1 - tail)),
        }
    return out


def main() -> None:
    started = time.time()
    df = modeling.load_clean_data()
    X, y = df[FIT_COLUMNS], df["price"]
    actual = y.to_numpy()
    folds = list(KFold(5, shuffle=True, random_state=SEED).split(X))
    print(f"{len(df):,} listings, scored with 5-fold cross-validation "
          f"(every listing is predicted by a model that never saw it)\n")

    # 1. Compare every candidate on the same folds.
    results, oof = {}, {}
    header = f"{'model':42s} {'R2':>6s} {'MAE (lakh)':>11s} {'median err':>11s} {'within 20%':>11s}"
    print(header + "\n" + "-" * len(header))
    for name, make in CANDIDATES.items():
        t0 = time.time()
        predicted = np.empty(len(X))
        fold_scores = []
        for train_idx, test_idx in folds:
            model = make().fit(X.iloc[train_idx], y.iloc[train_idx])
            predicted[test_idx] = model.predict(X.iloc[test_idx])
            fold_scores.append(score(actual[test_idx], predicted[test_idx]))
        oof[name] = predicted
        results[name] = {k: float(np.mean([s[k] for s in fold_scores])) for k in fold_scores[0]}
        results[name]["r2_std"] = float(np.std([s["r2"] for s in fold_scores]))
        results[name]["fit_seconds"] = round((time.time() - t0) / len(folds), 1)
        r = results[name]
        print(f"{name:42s} {r['r2']:6.3f} {r['mae_lakh']:11.1f} "
              f"{r['median_error_pct']:10.1f}% {r['within_20_pct']:10.1f}%")

    # 2. Train the final model on every listing.
    final = modeling.train_final_model(df)
    known = np.array([final.is_known_locality(c, l)
                      for c, l in zip(X["city"], X["locality"])])
    by_group = {
        "listed": score(actual[known], oof[CHOSEN][known]),
        "other": score(actual[~known], oof[CHOSEN][~known]),
    }
    by_group["listed"]["share_pct"] = float(known.mean() * 100)
    by_group["other"]["share_pct"] = float((~known).mean() * 100)

    # 3. Price range. Check the method on a held-out fifth of the data first,
    #    then measure the range that ships from all out-of-fold predictions.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED)
    check_model = PriceRegressor().fit(X_train, y_train)
    check_interval = interval_from_residuals(
        check_model, X_train, y_train.to_numpy(),
        out_of_fold(PriceRegressor, X_train, y_train))
    test_pred = check_model.predict(X_test)
    test_known = np.array([check_model.is_known_locality(c, l)
                           for c, l in zip(X_test["city"], X_test["locality"])])
    low = test_pred * np.exp(np.where(
        test_known, check_interval["listed"]["low"], check_interval["other"]["low"]))
    high = test_pred * np.exp(np.where(
        test_known, check_interval["listed"]["high"], check_interval["other"]["high"]))
    covered = (y_test.to_numpy() >= low) & (y_test.to_numpy() <= high)
    interval = interval_from_residuals(final, X, actual, oof[CHOSEN])
    interval["held_out_coverage_pct"] = float(covered.mean() * 100)
    print(f"\nPrice range: meant to contain {modeling.INTERVAL_COVERAGE:.0%} of real prices, "
          f"contained {covered.mean():.1%} of {len(X_test):,} held-out listings")

    # 4. Save everything.
    modeling.save_bundle(final, interval, len(df))
    catalog = modeling.build_catalog(df)
    paths.CATALOG_FILE.write_text(json.dumps(catalog, indent=1, ensure_ascii=False),
                                  encoding="utf-8")
    metrics = {
        "dataset": {
            "rows": int(len(df)), "cities": int(df["city"].nunique()),
            "named_localities": int(len(final.known_localities_)),
        },
        "evaluation": "5-fold cross-validation",
        "chosen": CHOSEN,
        "baseline": BASELINE,
        "models": results,
        "by_locality_type": by_group,
        "interval": interval,
        "sklearn_version": sklearn.__version__,
    }
    paths.METRICS_FILE.write_text(json.dumps(metrics, indent=2))
    print(f"Saved model, metrics and catalog to {paths.MODEL_DIR} "
          f"({time.time() - started:.0f}s)")


if __name__ == "__main__":
    main()
