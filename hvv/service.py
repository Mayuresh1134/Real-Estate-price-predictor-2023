"""What the screens call to get an estimate. No GUI code in here."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

from . import paths

OTHER_LABEL = "Other / not listed"
MIN_AREA, MAX_AREA = 200, 10_000
MIN_BHK, MAX_BHK = 1, 8


class InputError(ValueError):
    """A problem with what was typed. ``field`` says which input to point at."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class Estimate:
    city: str
    locality: str               # "Other" when the locality is not listed
    area_sqft: float
    bhk: int
    price: float
    low: float
    high: float
    known_locality: bool
    coverage: float             # share of real prices expected inside low..high
    locality_median_ppsf: int | None
    locality_listings: int | None
    city_median_ppsf: int
    city_listings: int

    @property
    def ppsf(self) -> float:
        return self.price / self.area_sqft

    @property
    def place(self) -> str:
        return f"{self.locality}, {self.city}" if self.known_locality else self.city


class PriceService:
    """Loads the catalog straight away and the model on first use."""

    def __init__(self):
        try:
            self.catalog = json.loads(paths.CATALOG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # models/catalog.json is missing or damaged: rebuild it from the data.
            from . import modeling
            self.catalog = modeling.build_catalog(modeling.load_clean_data())
            try:
                paths.MODEL_DIR.mkdir(exist_ok=True)
                paths.CATALOG_FILE.write_text(
                    json.dumps(self.catalog, indent=1, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        try:
            self.metrics = json.loads(paths.METRICS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.metrics = {}
        self._bundle = None

    # -- model ------------------------------------------------------------
    def load_model(self) -> None:
        """Slow (imports scikit-learn, may retrain). Safe to call from a thread."""
        if self._bundle is None:
            from . import modeling
            self._bundle = modeling.load_bundle()

    @property
    def model_ready(self) -> bool:
        return self._bundle is not None

    # -- catalog ----------------------------------------------------------
    def cities(self) -> list[str]:
        return sorted(self.catalog["cities"])

    def localities(self, city: str) -> list[str]:
        """Named localities of a city, then the catch-all option."""
        info = self.catalog["cities"].get(city)
        if not info:
            return []
        return sorted(info["localities"]) + [OTHER_LABEL]

    # -- estimating -------------------------------------------------------
    def validate(self, city, locality, area_text, bhk) -> tuple[str, str, float, int]:
        if city not in self.catalog["cities"]:
            raise InputError("city", "Choose a city from the list.")
        if not locality:
            raise InputError("locality", f"Choose a locality, or “{OTHER_LABEL}”.")
        if locality != OTHER_LABEL and locality not in self.catalog["cities"][city]["localities"]:
            raise InputError("locality", f"Choose a locality from the list, or “{OTHER_LABEL}”.")
        try:
            area = float(str(area_text).replace(",", "").strip())
        except ValueError:
            raise InputError("area", "Enter the area as a number, for example 1200.") from None
        if not math.isfinite(area) or not MIN_AREA <= area <= MAX_AREA:
            raise InputError(
                "area", f"Enter an area between {MIN_AREA:,} and {MAX_AREA:,} sq ft.")
        try:
            bhk = int(bhk)
        except (TypeError, ValueError):
            raise InputError("bhk", "Choose the number of bedrooms.") from None
        if not MIN_BHK <= bhk <= MAX_BHK:
            raise InputError("bhk", f"Bedrooms must be between {MIN_BHK} and {MAX_BHK}.")
        return city, locality, area, bhk

    def estimate(self, city, locality, area_text, bhk, *, under_construction=False,
                 rera=False, resale=True) -> Estimate:
        city, locality, area, bhk = self.validate(city, locality, area_text, bhk)
        self.load_model()
        import pandas as pd
        from .modeling import OTHER_LOCALITY

        model_locality = OTHER_LOCALITY if locality == OTHER_LABEL else locality
        row = pd.DataFrame([{
            "city": city, "locality": model_locality, "area_sqft": area, "bhk": bhk,
            "under_construction": int(bool(under_construction)),
            "rera": int(bool(rera)), "resale": int(bool(resale)),
        }])
        model = self._bundle["model"]
        price = float(model.predict(row)[0])
        known = model.is_known_locality(city, model_locality)
        spread = self._bundle["interval"]["listed" if known else "other"]

        city_info = self.catalog["cities"][city]
        loc_info = city_info["localities"].get(locality) if known else None
        return Estimate(
            city=city, locality=model_locality, area_sqft=area, bhk=bhk,
            price=price,
            low=price * math.exp(spread["low"]),
            high=price * math.exp(spread["high"]),
            known_locality=known,
            coverage=float(self._bundle["interval"].get("coverage", 0.8)),
            locality_median_ppsf=loc_info["median_ppsf"] if loc_info else None,
            locality_listings=loc_info["listings"] if loc_info else None,
            city_median_ppsf=city_info["median_ppsf"],
            city_listings=city_info["listings"],
        )
