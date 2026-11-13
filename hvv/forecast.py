"""Future value of a property that grows at a fixed yearly rate."""
from __future__ import annotations

from dataclasses import dataclass

MAX_YEARS = 40
MIN_RATE, MAX_RATE = -20.0, 40.0

# Average yearly growth of home prices, Q1 FY11 to Q1 FY21, as shown in the
# chart that shipped with the first version of this project (GrowthRate.png).
# They describe that decade only; they are offered as starting points.
HISTORICAL_GROWTH = {
    "All-India": 10.1,
    "Bangalore": 11.4,
    "Delhi": 11.6,
    "Kolkata": 12.5,
    "Lucknow": 15.0,
    "Mumbai": 10.7,
}


@dataclass(frozen=True)
class Forecast:
    present_value: float
    rate_pct: float
    years: int
    values: tuple[float, ...]      # values[0] is today, values[n] is after n years

    @property
    def future_value(self) -> float:
        return self.values[-1]

    @property
    def gain(self) -> float:
        return self.future_value - self.present_value

    @property
    def multiple(self) -> float:
        return self.future_value / self.present_value


def project(present_value: float, rate_pct: float, years: int) -> Forecast:
    """Compound growth: value after n years = present value x (1 + rate) ** n."""
    if present_value <= 0:
        raise ValueError("Present value must be more than zero.")
    if not MIN_RATE <= rate_pct <= MAX_RATE:
        raise ValueError(f"Growth rate must be between {MIN_RATE:g}% and {MAX_RATE:g}% a year.")
    if int(years) != years or not 1 <= years <= MAX_YEARS:
        raise ValueError(f"Number of years must be a whole number from 1 to {MAX_YEARS}.")
    factor = 1 + rate_pct / 100
    values = tuple(present_value * factor ** n for n in range(int(years) + 1))
    return Forecast(float(present_value), float(rate_pct), int(years), values)
