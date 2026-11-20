"""Check the data before anything is built from it (make validate).

Two kinds of check, reported separately:

* **Rules** hold for any release of this data: keys are present and unique, the label is 0 or 1, flags are 0/1 or Y/N,
  normalised scores lie in [0, 1], past dates are not after the application, counts are not negative, every column
  matches the leakage table, and every related row points at a known applicant. A rule failure means the data is wrong.
* **Profile** is the release this project was built on, recorded in `configs/data_contract.json`: row counts, columns,
  types, missing counts, minimum and maximum, category levels, and the size and SHA-256 of each raw CSV. A profile
  difference means the data is *different* (another download, or a changed conversion), so every number in the
  reports may move. If the change is intended, re-record with `--write` and say so in the decision log.

The checks read one column at a time with pyarrow, so they fit in 4 GB.

Usage:
  python -m credit_risk.data.validate           check; exit code 1 on any failure
  python -m credit_risk.data.validate --write   record the current data as the contract (on purpose only)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from credit_risk.data.interim import TABLES
from credit_risk.paths import AVAILABILITY, INTERIM, NO_DATE, RAW

CONTRACT = Path("configs/data_contract.json")
ARCHIVE = Path("data/home-credit-default-risk.zip")
MAX_LEVELS = 100            # category levels are recorded in full up to this many
SCORE_TOLERANCE = 1e-3      # RATE_DOWN_PAYMENT has float noise just below 0
UNIQUE_KEYS = {"application_train": "SK_ID_CURR", "application_test": "SK_ID_CURR",
               "bureau": "SK_ID_BUREAU", "previous_application": "SK_ID_PREV"}
CHILD_TABLES = ["bureau", "previous_application", "POS_CASH_balance", "installments_payments", "credit_card_balance"]
WEEKDAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}
BUILDING_SUFFIXES = ("_AVG", "_MODE", "_MEDI")
# Rule breaks that are known, counted and handled downstream. The count is pinned by the profile (the column's min
# or max), so a new break of the same rule still fails.
KNOWN_EXCEPTIONS = {
    ("application_test", "REGION_RATING_CLIENT_W_CITY"): "rating -1 in 1 row; recoded to missing in clean.py (D60)",
}
NONNEGATIVE_PREFIXES = ("CNT_", "AMT_REQ_CREDIT_BUREAU_", "SK_DPD", "OBS_", "DEF_")


# ---------------------------------------------------------------- reading

def _kind(t: pa.DataType) -> str:
    if pa.types.is_integer(t):
        return "int"
    if pa.types.is_floating(t):
        return "float"
    if pa.types.is_string(t) or pa.types.is_large_string(t) or pa.types.is_dictionary(t):
        return "string"
    return str(t)


def _column(path: Path, name: str) -> pa.ChunkedArray:
    return pq.read_table(path, columns=[name]).column(0)


def _names(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema_arrow.names)


def _levels(col: pa.ChunkedArray) -> list[str]:
    return sorted(pc.unique(col.drop_null()).to_pylist())


def _count(mask) -> int:
    return int(pc.sum(mask).as_py() or 0)


# ---------------------------------------------------------------- profile

def profile_table(path: Path) -> dict:
    pf = pq.ParquetFile(path)
    cols = {}
    for field in pf.schema_arrow:
        col = _column(path, field.name)
        entry = {"type": _kind(field.type), "nulls": int(col.null_count)}
        if entry["type"] in ("int", "float"):
            mm = pc.min_max(col)
            entry["min"], entry["max"] = mm["min"].as_py(), mm["max"].as_py()
        elif entry["type"] == "string":
            levels = _levels(col)
            entry["n_levels"] = len(levels)
            if len(levels) <= MAX_LEVELS:
                entry["levels"] = levels
        cols[field.name] = entry
    return {"rows": pf.metadata.num_rows, "columns": cols}


def sha256(path: Path, block: int = 1 << 23) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(block):
            h.update(chunk)
    return h.hexdigest()


def profile(interim: Path, raw: Path | None) -> dict:
    out = {"tables": {t: profile_table(interim / f"{t}.parquet") for t in TABLES}}
    if raw is not None and raw.exists():
        out["raw_csv"] = {t: {"bytes": (raw / f"{t}.csv").stat().st_size, "sha256": sha256(raw / f"{t}.csv")}
                          for t in TABLES}
    return out


def compare(contract: dict, current: dict, per_table: int = 15) -> list[str]:
    """Differences between the recorded release and the current data, at most `per_table` lines per table."""
    diffs = []
    for t, want in contract["tables"].items():
        have = current["tables"].get(t)
        lines = []
        if have is None:
            diffs.append(f"{t}: table missing")
            continue
        if have["rows"] != want["rows"]:
            lines.append(f"{t}: {have['rows']:,} rows, recorded {want['rows']:,}")
        missing = [c for c in want["columns"] if c not in have["columns"]]
        extra = [c for c in have["columns"] if c not in want["columns"]]
        if missing:
            lines.append(f"{t}: columns missing: {', '.join(missing)}")
        if extra:
            lines.append(f"{t}: unexpected columns: {', '.join(extra)}")
        for c, w in want["columns"].items():
            h = have["columns"].get(c)
            if h is None:
                continue
            for key in ("type", "nulls", "min", "max", "n_levels", "levels"):
                if key in w and w.get(key) != h.get(key):
                    shown = (f"{len(set(h.get(key) or []) ^ set(w[key]))} levels differ" if key == "levels"
                             else f"{h.get(key)!r}, recorded {w[key]!r}")
                    lines.append(f"{t}.{c}: {key} {shown}")
                    break
        if len(lines) > per_table:
            lines = lines[:per_table] + [f"{t}: ... and {len(lines) - per_table} more"]
        diffs += lines
    for t, want in contract.get("raw_csv", {}).items():
        have = current.get("raw_csv", {}).get(t)
        if have is not None and have != want:
            diffs.append(f"raw {t}.csv: SHA-256 {have['sha256'][:12]}..., recorded {want['sha256'][:12]}...")
    return diffs


# ---------------------------------------------------------------- rules

def check_rules(interim: Path, availability: Path = AVAILABILITY) -> tuple[list[str], list[str]]:
    """Return (failures, notes). Notes describe rows the pipeline is known to handle."""
    fails, notes = [], []
    av = pd.read_csv(availability)
    verdict = {(r.table, r.column): r.verdict for r in av.itertuples()}
    by_name = {r.column: r.verdict for r in av[av.table == "application_train"].itertuples()}
    paths = {t: interim / f"{t}.parquet" for t in TABLES}
    names = {t: _names(p) for t, p in paths.items()}

    # Columns: the training tables match the leakage table exactly; Kaggle's test is train minus the label.
    for t in TABLES:
        if t == "application_test":
            want = [c for c in names["application_train"] if c != "TARGET"]
        else:
            want = av.loc[av.table == t, "column"].tolist()
        if set(names[t]) != set(want):
            fails.append(f"{t}: columns differ from the leakage table "
                         f"(missing {sorted(set(want) - set(names[t]))}, extra {sorted(set(names[t]) - set(want))})")

    # Keys: never missing; unique at the table's grain.
    for t in TABLES:
        for c in [c for c in names[t] if c.startswith("SK_ID_")]:
            n = _column(paths[t], c).null_count
            if n:
                fails.append(f"{t}.{c}: {n:,} missing keys")
    ids = {}
    for t, key in UNIQUE_KEYS.items():
        col = _column(paths[t], key)
        n_unique = len(pc.unique(col))
        if n_unique != len(col):
            fails.append(f"{t}.{key}: {len(col) - n_unique:,} repeated keys")
        if key == "SK_ID_CURR":
            ids[t] = pc.unique(col)
    overlap = _count(pc.is_in(ids["application_train"], value_set=ids["application_test"]))
    if overlap:
        fails.append(f"{overlap:,} applicants are in both application_train and application_test")
    known = pa.concat_arrays([ids["application_train"], ids["application_test"]])
    for t in CHILD_TABLES:
        orphans = _count(pc.invert(pc.is_in(_column(paths[t], "SK_ID_CURR"), value_set=known)))
        if orphans:
            fails.append(f"{t}: {orphans:,} rows point at no known applicant")

    # Label.
    target = _column(paths["application_train"], "TARGET")
    if target.null_count or set(_levels(target)) - {0, 1}:
        fails.append("application_train.TARGET: not a 0/1 label with no gaps")

    # Values, by what the column is.
    for t in TABLES:
        for c in names[t]:
            v = verdict.get((t, c), by_name.get(c) if t == "application_test" else None)
            col = _column(paths[t], c)
            kind = _kind(col.type)
            label = f"{t}.{c}"
            if kind == "string":
                levels = set(_levels(col))
                if c.startswith("FLAG_") and levels - {"Y", "N"}:
                    fails.append(f"{label}: flag levels {sorted(levels)}")
                if c.startswith("WEEKDAY_") and levels - WEEKDAYS:
                    fails.append(f"{label}: unknown weekdays {sorted(levels - WEEKDAYS)}")
                if c == "CODE_GENDER" and levels - {"F", "M", "XNA"}:
                    fails.append(f"{label}: unknown levels {sorted(levels - {'F', 'M', 'XNA'})}")
                continue
            if kind not in ("int", "float"):
                continue
            mm = pc.min_max(col)
            lo, hi = mm["min"].as_py(), mm["max"].as_py()
            if lo is None:
                continue
            if c.startswith(("FLAG_", "NFLAG_", "REG_", "LIVE_")) and (lo < 0 or hi > 1 or
                                                                      _count(pc.not_equal(col, pc.round(col)))):
                fails.append(f"{label}: flag outside 0/1 ({lo}..{hi})")
            normalised = (c.startswith(("EXT_SOURCE_", "RATE_")) or c == "REGION_POPULATION_RELATIVE"
                          or (t.startswith("application") and c.endswith(BUILDING_SUFFIXES)))
            if normalised and (lo < -SCORE_TOLERANCE or hi > 1 + SCORE_TOLERANCE):
                fails.append(f"{label}: normalised score outside [0, 1] ({lo:.4g}..{hi:.4g})")
            if c.startswith(NONNEGATIVE_PREFIXES) and lo < 0:
                fails.append(f"{label}: negative count ({lo})")
            if c.startswith("REGION_RATING_") and (lo < 1 or hi > 3):
                if (t, c) in KNOWN_EXCEPTIONS:
                    notes.append(f"{label}: {KNOWN_EXCEPTIONS[(t, c)]}")
                else:
                    fails.append(f"{label}: rating outside 1-3")
            if c.startswith("HOUR_") and (lo < 0 or hi > 23):
                fails.append(f"{label}: hour outside 0-23")
            if t.startswith("application") and c.startswith("AMT_") and lo < 0:
                fails.append(f"{label}: negative amount ({lo})")
            if c == "DAYS_BIRTH" and not (-100 * 365.25 <= lo and hi <= -18 * 365.25):
                fails.append(f"{label}: ages outside 18-100 years")
            if c.startswith("DAYS_") or c == "MONTHS_BALANCE":
                after = _count(pc.and_(pc.greater(col, 0), pc.not_equal(col, NO_DATE)))
                if not after or v == "ok_planned":
                    continue
                if v == "ok_filter":
                    notes.append(f"{label}: {after:,} rows dated after the application (dropped by the pipeline)")
                else:
                    fails.append(f"{label}: {after:,} rows dated after the application")
    return fails, notes


# ---------------------------------------------------------------- main

def run(interim: Path = INTERIM, raw: Path | None = RAW, contract_path: Path = CONTRACT,
        availability: Path = AVAILABILITY) -> int:
    fails, notes = check_rules(interim, availability)
    current = profile(interim, raw)
    contract = json.loads(contract_path.read_text())
    diffs = compare(contract, current)
    if "raw_csv" not in current:
        notes.append("raw CSVs not available here: their hashes were not checked")
    n_cols = sum(len(t["columns"]) for t in current["tables"].values())
    print(f"Checked {len(TABLES)} tables, {n_cols} columns, "
          f"{sum(t['rows'] for t in current['tables'].values()):,} rows.")
    for n in notes:
        print("  note:", n)
    for title, items in (("Rule failures (the data is wrong)", fails),
                         (f"Profile differences (the data is not the release in {contract_path})", diffs)):
        print(f"{title}: {len(items)}")
        for i in items:
            print("  -", i)
    return 1 if fails or diffs else 0


def write(interim: Path = INTERIM, raw: Path = RAW, contract_path: Path = CONTRACT) -> None:
    current = profile(interim, raw)
    if ARCHIVE.exists():
        current["archive"] = {"file": ARCHIVE.name, "bytes": ARCHIVE.stat().st_size, "sha256": sha256(ARCHIVE)}
    current = {"note": "Recorded by `python -m credit_risk.data.validate --write`; checked by `make validate`.",
               **current}
    contract_path.write_text(json.dumps(current, indent=1) + "\n")
    print(f"Recorded {len(current['tables'])} tables in {contract_path}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Check the interim and raw data against rules and the recorded release.")
    ap.add_argument("--interim", default=INTERIM, type=Path)
    ap.add_argument("--raw", default=RAW, type=Path)
    ap.add_argument("--contract", default=CONTRACT, type=Path)
    ap.add_argument("--write", action="store_true", help="record the current data as the contract")
    a = ap.parse_args(argv)
    if a.write:
        write(a.interim, a.raw, a.contract)
    else:
        sys.exit(run(a.interim, a.raw, a.contract))


if __name__ == "__main__":
    main()
