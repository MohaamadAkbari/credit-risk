"""End to end on generated mini-tables: stage tables nest (A in B in C), one row per applicant,
no label or protected column, and the audit table is separate."""
from pathlib import Path

import numpy as np
import pandas as pd

from credit_risk.features import application, audit, bureau, installments, monthly, previous
from credit_risk.features.build import build_all

AVAIL = Path(__file__).resolve().parents[1] / "configs" / "feature_availability.csv"
N = 40
VALUES = {"CREDIT_ACTIVE": ["Active", "Closed"], "CREDIT_CURRENCY": ["currency 1"], "STATUS": ["0", "1", "C", "X"],
          "NAME_CONTRACT_STATUS": ["Approved", "Refused", "Active"], "CODE_GENDER": ["F", "M"],
          "NAME_CONTRACT_TYPE": ["Cash loans", "Revolving loans"]}


def _table(columns, kinds, n, rng):
    data = {}
    for c in columns:
        if c == "SK_ID_CURR":
            data[c] = rng.integers(0, N, n) + 100_000
        elif c.startswith("SK_ID_"):
            data[c] = rng.integers(0, n // 2 + 1, n) + 1_000_000
        elif kinds.get(c) == "text" or c in VALUES:
            data[c] = pd.Series(rng.choice(VALUES.get(c, ["x", "y"]), n), dtype="string")
        elif c.startswith(("DAYS_", "MONTHS_")):
            data[c] = -rng.integers(1, 2000, n).astype("float32")
        else:
            data[c] = rng.random(n).astype("float32")
    return pd.DataFrame(data)


def test_build_all_on_mini_tables(tmp_path):
    rng = np.random.default_rng(0)
    avail = pd.read_csv(AVAIL)
    kinds = {r.column: ("text" if pd.isna(r.min) else "num") for r in avail.itertuples()}
    interim = tmp_path / "interim"
    interim.mkdir()
    need = {}
    for src in [application.sources(AVAIL), bureau.SOURCES, previous.SOURCES, installments.SOURCES,
                monthly.SOURCES, audit.SOURCES, {"application_train": ["TARGET"]}]:
        for t, cols in src.items():
            need.setdefault(t, set()).update(cols)
    for t, cols in need.items():
        n = N if t == "application_train" else 200
        df = _table(sorted(cols), kinds, n, rng)
        if t == "application_train":
            df["SK_ID_CURR"] = np.arange(N) + 100_000
        df.to_parquet(interim / f"{t}.parquet")

    out = tmp_path / "processed"
    m = build_all(interim, out, AVAIL)
    a, b, c = (pd.read_parquet(out / f"features_{s}.parquet") for s in "ABC")
    assert len(a) == len(b) == len(c) == N and c.index.is_unique
    assert set(a.columns) < set(b.columns) < set(c.columns)
    assert not set(c.columns) & {"TARGET", "CODE_GENDER", "DAYS_BIRTH", "GENDER", "AGE", "AGE_BAND"}
    assert c.filter(like="_COUNT").isna().sum().sum() == 0          # no rows in a table = zero, not missing
    assert set(pd.read_parquet(out / "audit.parquet").columns) == {"GENDER", "AGE", "AGE_BAND", "THIN_FILE", "CONTRACT_TYPE"}
    assert m["stages"]["C"]["features"] == c.shape[1]
