"""Default locations, relative to the repository root (the Makefile runs from there)."""
from pathlib import Path

RAW = Path("data/home-credit-default-risk")
INTERIM = Path("data/interim")
PROCESSED = Path("data/processed")
AVAILABILITY = Path("configs/feature_availability.csv")
SPLIT_MANIFEST = Path("configs/split_manifest.json")
FEATURE_MANIFEST = Path("configs/feature_manifest.json")

NO_DATE = 365243  # Home Credit's "no date" marker in DAYS_ columns
