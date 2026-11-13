"""Locations of the files the project reads and writes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
RAW_DATA = DATA_DIR / "raw" / "india_housing_listings.csv"
CLEAN_DATA = DATA_DIR / "housing_clean.csv"

MODEL_DIR = ROOT / "models"
MODEL_FILE = MODEL_DIR / "price_model.joblib"
METRICS_FILE = MODEL_DIR / "metrics.json"
CATALOG_FILE = MODEL_DIR / "catalog.json"

ASSETS_DIR = ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

# Per-machine files (accounts, settings). Never committed to git.
APP_DATA_DIR = ROOT / "app_data"
USERS_FILE = APP_DATA_DIR / "users.json"
SETTINGS_FILE = APP_DATA_DIR / "settings.json"
