"""Build the feature tables for ablation stages A, B and C, plus the audit table.

Outputs (data/processed/, not committed):
  features_A.parquet   application form only
  features_B.parquet   + credit-bureau information: bureau, bureau_balance and the bureau-derived
                       main-table columns (D50)
  features_C.parquet   + earlier Home Credit applications, instalments, POS and card months
  audit.parquet        gender, age band, thin file, product: for fairness slices, never a model input
Committed: configs/feature_manifest.json (row counts, feature names per block, coverage, and a content
fingerprint of each output file). Later phases read the tables with `load_stage`, which refuses a table whose
fingerprint differs from the manifest, so every result can be tied to the exact features it used.

Usage: python -m credit_risk.features.build           build (make features)
       python -m credit_risk.features.build --check   recompute the fingerprints and compare (make verify)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd

from credit_risk.data.io import load
from credit_risk.features import application, audit, bureau, installments, monthly, previous
from credit_risk.paths import AVAILABILITY, FEATURE_MANIFEST, INTERIM, PROCESSED

STAGES = {"A": ["application"],
          "B": ["application", "application_bureau", "bureau"],
          "C": ["application", "application_bureau", "bureau", "previous", "installments", "pos", "credit_card"]}


def _builders(availability: Path, bb_max_month: int):
    return {"application": lambda i: application.build(i, availability),
            "application_bureau": lambda i: application.build_bureau(i, availability),
            "bureau": lambda i: bureau.build(i, bb_max_month),
            "previous": previous.build, "installments": installments.build,
            "pos": monthly.build_pos, "credit_card": monthly.build_cc}


OUTPUTS = [f"features_{s}" for s in STAGES] + ["audit"]


def fingerprint(df: pd.DataFrame) -> str:
    """SHA-256 of a table's content: column names and types, index, and every value.

    Hashes values rather than file bytes, so it does not change with the Parquet writer's version or compression.
    """
    h = hashlib.sha256()
    h.update(json.dumps([df.index.name] + [[c, str(t)] for c, t in df.dtypes.items()]).encode())
    h.update(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes())
    return h.hexdigest()


def _write(df: pd.DataFrame, path: Path) -> dict:
    df.to_parquet(path)
    back = pd.read_parquet(path)            # fingerprint what readers will get
    return {"rows": len(back), "columns": back.shape[1], "sha256": fingerprint(back)}


def check(processed: Path = PROCESSED, manifest: Path = FEATURE_MANIFEST) -> list[str]:
    """Outputs whose content differs from the fingerprints in the manifest (empty list = all match)."""
    files = json.loads(Path(manifest).read_text())["files"]
    bad = []
    for name, want in files.items():
        path = Path(processed) / f"{name}.parquet"
        if not path.exists():
            bad.append(f"{name}: missing ({path})")
        elif (got := fingerprint(pd.read_parquet(path))) != want["sha256"]:
            bad.append(f"{name}: fingerprint {got[:12]}..., manifest {want['sha256'][:12]}...")
    return bad


def load_stage(stage: str, processed: Path = PROCESSED, manifest: Path = FEATURE_MANIFEST) -> pd.DataFrame:
    """Read features_{stage} (or "audit"), refusing it if it is not the table recorded in the manifest."""
    name = stage if stage == "audit" else f"features_{stage}"
    df = pd.read_parquet(Path(processed) / f"{name}.parquet")
    want = json.loads(Path(manifest).read_text())["files"][name]["sha256"]
    if fingerprint(df) != want:
        raise ValueError(f"{name} differs from {manifest}: rebuild with `make features`, or commit the new manifest "
                         "if the change is intended")
    return df


def _tidy(block: pd.DataFrame, ids: pd.Index, name: str) -> pd.DataFrame:
    block = block.reindex(ids)
    if name not in ("application", "application_bureau"):
        # No rows in the source table means zero credits / zero amounts, not "unknown".
        zero = [c for c in block.columns if c.endswith(("_COUNT", "_SUM"))]
        block[zero] = block[zero].fillna(0)
    num = block.select_dtypes("number").columns
    block[num] = block[num].astype("float32")
    return block


def build_all(interim: Path, out: Path, availability: Path = AVAILABILITY, bb_max_month: int = 0) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    ids = pd.Index(load(interim, "application_train", ["SK_ID_CURR"]).SK_ID_CURR, name="SK_ID_CURR")
    blocks, timing, covered = {}, {}, {}
    for name, fn in _builders(availability, bb_max_month).items():
        t0 = time.time()
        raw = fn(interim)
        covered[name] = int(ids.isin(raw.index).sum())           # applicants with at least one source row
        blocks[name] = _tidy(raw, ids, name)
        del raw
        timing[name] = round(time.time() - t0, 1)
        print(f"{name:>12}: {blocks[name].shape[1]:>3} features in {timing[name]}s")
    files = {}
    for stage, names in STAGES.items():
        files[f"features_{stage}"] = _write(pd.concat([blocks[n] for n in names], axis=1),
                                            out / f"features_{stage}.parquet")
    files["audit"] = _write(audit.build(interim).reindex(ids), out / "audit.parquet")
    return {
        "rows": len(ids), "bureau_balance_max_month": bb_max_month,
        "stages": {s: {"blocks": n, "features": int(sum(blocks[b].shape[1] for b in n))} for s, n in STAGES.items()},
        "blocks": {n: {"applicants_with_source_rows": covered[n], "features": list(b.columns)}
                   for n, b in blocks.items()},
        "files": files,
        "seconds": timing,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build the stage A/B/C feature tables.")
    ap.add_argument("--interim", default=INTERIM, type=Path)
    ap.add_argument("--out", default=PROCESSED, type=Path)
    ap.add_argument("--availability", default=AVAILABILITY, type=Path)
    ap.add_argument("--bb-max-month", default=0, type=int, help="0 includes the application month; -1 excludes it")
    ap.add_argument("--manifest", default=FEATURE_MANIFEST, type=Path)
    ap.add_argument("--check", action="store_true", help="compare data/processed with the manifest; build nothing")
    a = ap.parse_args(argv)
    if a.check:
        bad = check(a.out, a.manifest)
        print("\n".join(bad) if bad else f"All {len(OUTPUTS)} tables match {a.manifest}")
        sys.exit(1 if bad else 0)
    m = build_all(a.interim, a.out, a.availability, a.bb_max_month)
    m.pop("seconds")
    a.manifest.write_text(json.dumps(m, indent=1) + "\n")
    print({s: v["features"] for s, v in m["stages"].items()})


if __name__ == "__main__":
    main()
