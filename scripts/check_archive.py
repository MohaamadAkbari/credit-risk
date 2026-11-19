"""Check the downloaded Kaggle archive against the SHA-256 recorded in configs/data_contract.json.

Standard library only, so `make data` can run it before the package is installed.
Usage: python scripts/check_archive.py [ZIP] [CONTRACT]
"""
import hashlib
import json
import sys
from pathlib import Path

zip_path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/home-credit-default-risk.zip")
contract = Path(sys.argv[2] if len(sys.argv) > 2 else "configs/data_contract.json")
want = json.loads(contract.read_text())["archive"]["sha256"]
h = hashlib.sha256()
with open(zip_path, "rb") as f:
    while chunk := f.read(1 << 23):
        h.update(chunk)
if h.hexdigest() != want:
    sys.exit(f"{zip_path}: SHA-256 {h.hexdigest()} differs from the release this project was built on ({want}).\n"
             "The numbers in the reports may not reproduce. See data/README.md.")
print(f"{zip_path}: SHA-256 matches configs/data_contract.json")
