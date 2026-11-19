"""Train / validation / test split by applicant (D20), locked by a manifest.

The split is stratified on TARGET with a fixed seed. Its manifest (counts, default rates and a
SHA-256 of each fold's sorted IDs) is committed in configs/split_manifest.json. Rebuilding the
split must reproduce the same fingerprints, so the test set cannot change without anyone noticing.

Usage: python -m credit_risk.data.split   (or: make split)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from credit_risk.data.io import load
from credit_risk.paths import INTERIM, PROCESSED, SPLIT_MANIFEST

SEED = 42
SHARES = {"train": 0.70, "valid": 0.15, "test": 0.15}


def make_split(labels: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """labels: SK_ID_CURR, TARGET -> SK_ID_CURR, TARGET, fold."""
    labels = labels.sort_values("SK_ID_CURR").reset_index(drop=True)   # row order must not change the split
    rest, test = train_test_split(labels, test_size=SHARES["test"], stratify=labels["TARGET"], random_state=seed)
    valid_share = SHARES["valid"] / (SHARES["train"] + SHARES["valid"])
    train, valid = train_test_split(rest, test_size=valid_share, stratify=rest["TARGET"], random_state=seed)
    out = pd.concat([train.assign(fold="train"), valid.assign(fold="valid"), test.assign(fold="test")])
    return out.sort_values("SK_ID_CURR").reset_index(drop=True)


def fingerprint(ids: pd.Series) -> str:
    return hashlib.sha256(",".join(map(str, sorted(ids.astype(int)))).encode()).hexdigest()


def manifest(split: pd.DataFrame, seed: int = SEED) -> dict:
    folds = {}
    for f in SHARES:
        part = split[split.fold == f]
        folds[f] = {"rows": int(len(part)), "defaults": int(part.TARGET.sum()),
                    "default_rate": round(float(part.TARGET.mean()), 5), "sha256_ids": fingerprint(part.SK_ID_CURR)}
    return {"seed": seed, "shares": SHARES, "stratified_on": "TARGET", "unit": "SK_ID_CURR", "folds": folds}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build and lock the train/valid/test split.")
    ap.add_argument("--interim", default=INTERIM, type=Path)
    ap.add_argument("--out", default=PROCESSED, type=Path)
    ap.add_argument("--manifest", default=SPLIT_MANIFEST, type=Path)
    ap.add_argument("--relock", action="store_true", help="Accept a new split and overwrite the manifest")
    a = ap.parse_args(argv)
    labels = load(a.interim, "application_train", ["SK_ID_CURR", "TARGET"])
    labels["TARGET"] = labels["TARGET"].astype("int8")
    split = make_split(labels)
    new = manifest(split)
    if a.manifest.exists() and not a.relock:
        old = json.loads(a.manifest.read_text())
        changed = [f for f in SHARES if old["folds"][f]["sha256_ids"] != new["folds"][f]["sha256_ids"]]
        if changed:
            raise SystemExit(f"Split differs from the locked manifest for {changed}. "
                             "Investigate, or rerun with --relock if the change is intended.")
    a.out.mkdir(parents=True, exist_ok=True)
    split.to_parquet(a.out / "split.parquet", index=False)
    a.manifest.write_text(json.dumps(new, indent=2) + "\n")
    for f, m in new["folds"].items():
        print(f"{f:>5}: {m['rows']:>7,} rows, default rate {m['default_rate']:.2%}")


if __name__ == "__main__":
    main()
