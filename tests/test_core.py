"""Tests for everything that is not a screen. Run with:  python -m pytest"""
import json

import pytest

from hvv import forecast, formatting, paths
from hvv.auth import AuthError, UserStore
from hvv.service import OTHER_LABEL, InputError, PriceService


# -- formatting -------------------------------------------------------------
@pytest.mark.parametrize("n, expected", [
    (0, "0"), (999, "999"), (1000, "1,000"), (100000, "1,00,000"),
    (1234567, "12,34,567"), (123456789, "12,34,56,789"), (-4500000, "-45,00,000"),
])
def test_group_indian(n, expected):
    assert formatting.group_indian(n) == expected


def test_compact_rupees():
    assert formatting.compact_rupees(7_850_000) == "₹78.5 Lakh"
    assert formatting.compact_rupees(12_400_000) == "₹1.24 Cr"
    assert formatting.compact_rupees(85_000) == "₹85,000"


@pytest.mark.parametrize("text, expected", [
    ("7850000", 7_850_000), ("78,50,000", 7_850_000), ("₹ 78.5 lakh", 7_850_000),
    ("1.2 Cr", 12_000_000), ("45 lacs", 4_500_000), ("Rs. 50,00,000", 5_000_000),
])
def test_parse_amount(text, expected):
    assert formatting.parse_amount(text) == pytest.approx(expected)


def test_parse_amount_rejects_words():
    with pytest.raises(ValueError):
        formatting.parse_amount("a lot")


# -- forecast ---------------------------------------------------------------
def test_forecast_compounds():
    f = forecast.project(5_000_000, 10, 2)
    assert f.values == pytest.approx((5_000_000, 5_500_000, 6_050_000))
    assert f.future_value == pytest.approx(6_050_000)
    assert f.gain == pytest.approx(1_050_000)
    assert f.multiple == pytest.approx(1.21)


def test_forecast_accepts_falling_prices():
    assert forecast.project(1_000_000, -5, 1).future_value == pytest.approx(950_000)


@pytest.mark.parametrize("args", [(0, 10, 5), (-1, 10, 5), (1e6, 80, 5), (1e6, 10, 0),
                                  (1e6, 10, 2.5), (1e6, 10, 99)])
def test_forecast_rejects_bad_input(args):
    with pytest.raises(ValueError):
        forecast.project(*args)


# -- accounts ---------------------------------------------------------------
def test_register_then_sign_in(tmp_path):
    store = UserStore(tmp_path / "users.json")
    assert not store.has_accounts()
    store.register("Mayuresh", "correct horse", "correct horse")
    assert store.sign_in("mayuresh", "correct horse") == "Mayuresh"   # name is case-insensitive
    with pytest.raises(AuthError):
        store.sign_in("Mayuresh", "wrong password")
    with pytest.raises(AuthError):
        store.sign_in("nobody", "correct horse")


def test_passwords_are_not_stored(tmp_path):
    path = tmp_path / "users.json"
    UserStore(path).register("Asha", "s3cret-pass", "s3cret-pass")
    assert "s3cret-pass" not in path.read_text()
    record = json.loads(path.read_text())["asha"]
    assert set(record) == {"name", "salt", "hash", "iterations"}


@pytest.mark.parametrize("name, pw, confirm", [
    ("ab", "longenough", "longenough"),            # name too short
    ("Username!", "longenough", "longenough"),     # bad character
    ("Ravi", "short", "short"),                    # password too short
    ("Ravi", "longenough", "different1"),          # mismatch
])
def test_register_rejects(tmp_path, name, pw, confirm):
    with pytest.raises(AuthError):
        UserStore(tmp_path / "users.json").register(name, pw, confirm)


def test_duplicate_username(tmp_path):
    store = UserStore(tmp_path / "users.json")
    store.register("Ravi", "longenough", "longenough")
    with pytest.raises(AuthError):
        store.register("RAVI", "another-pass", "another-pass")


def test_unreadable_file_is_not_wiped(tmp_path):
    path = tmp_path / "users.json"
    path.write_text("{not json")
    with pytest.raises(AuthError):
        UserStore(path).register("Ravi", "longenough", "longenough")
    assert path.read_text() == "{not json"


# -- estimates --------------------------------------------------------------
@pytest.fixture(scope="module")
def service():
    s = PriceService()
    s.load_model()
    return s


def test_catalog(service):
    cities = service.cities()
    assert "Bangalore" in cities and "Mumbai" in cities and "Pune" in cities
    assert cities == sorted(cities)
    localities = service.localities("Pune")
    assert localities[-1] == OTHER_LABEL and len(localities) > 10
    assert service.localities("Atlantis") == []


def test_estimate_is_sane(service):
    locality = service.localities("Pune")[0]
    e = service.estimate("Pune", locality, "1,000", 2)
    assert e.known_locality and e.low < e.price < e.high
    assert 2_000 < e.ppsf < 30_000              # rupees per sq ft, plausible for Pune
    assert e.locality_median_ppsf and e.locality_listings >= 5


def test_bigger_home_costs_more(service):
    locality = service.localities("Bangalore")[0]
    prices = [service.estimate("Bangalore", locality, area, 2).price
              for area in (700, 1000, 1400, 2000)]
    assert prices == sorted(prices)


def test_other_locality_has_wider_range(service):
    named = service.estimate("Mumbai", service.localities("Mumbai")[0], 900, 2)
    other = service.estimate("Mumbai", OTHER_LABEL, 900, 2)
    assert not other.known_locality and other.locality_median_ppsf is None
    assert (other.high / other.low) > (named.high / named.low)


@pytest.mark.parametrize("city, locality, area, bhk, field", [
    ("Atlantis", "Anywhere", 1000, 2, "city"),
    ("Pune", "", 1000, 2, "locality"),
    ("Pune", "Not A Real Place", 1000, 2, "locality"),
    ("Pune", OTHER_LABEL, "abc", 2, "area"),
    ("Pune", OTHER_LABEL, "", 2, "area"),
    ("Pune", OTHER_LABEL, 50, 2, "area"),
    ("Pune", OTHER_LABEL, 50_000, 2, "area"),
    ("Pune", OTHER_LABEL, 1000, None, "bhk"),
    ("Pune", OTHER_LABEL, 1000, 12, "bhk"),
])
def test_estimate_rejects_bad_input(service, city, locality, area, bhk, field):
    with pytest.raises(InputError) as err:
        service.estimate(city, locality, area, bhk)
    assert err.value.field == field


def test_metrics_beat_the_baseline():
    m = json.loads(paths.METRICS_FILE.read_text())
    chosen, baseline = m["models"][m["chosen"]], m["models"][m["baseline"]]
    assert chosen["r2"] > baseline["r2"] + 0.3
    assert chosen["median_error_pct"] < baseline["median_error_pct"] / 2
