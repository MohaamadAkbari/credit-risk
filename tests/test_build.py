"""End to end on generated mini-tables: stage tables nest (A in B in C), one row per applicant,
no label or protected column, and the audit table is separate."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from credit_risk.features import application, audit, bureau, installments, monthly, previous
from credit_risk.features.build import build_all, check, fingerprint, load_stage

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
    for src in [application.sources(AVAIL), application.bureau_sources(AVAIL), bureau.SOURCES, previous.SOURCES, installments.SOURCES,
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
    assert set(m["files"]) == {"features_A", "features_B", "features_C", "audit"}
    assert m["files"]["features_C"]["sha256"] == fingerprint(c)


def test_fingerprint_follows_content_not_storage():
    df = pd.DataFrame({"X": [1.0, np.nan, 3.0], "C": pd.Categorical(["a", "b", "a"])},
                      index=pd.Index([1, 2, 3], name="SK_ID_CURR"))
    same = df.copy()
    same["C"] = same["C"].cat.reorder_categories(["b", "a"])           # same values, other category order
    assert fingerprint(df) == fingerprint(same)
    changed = df.copy()
    changed.loc[3, "X"] = 3.0001
    assert fingerprint(changed) != fingerprint(df)
    assert fingerprint(df.rename(columns={"X": "Y"})) != fingerprint(df)


def test_check_and_load_stage_refuse_a_changed_table(tmp_path):
    df = pd.DataFrame({"X": [1.0, 2.0]}, index=pd.Index([1, 2], name="SK_ID_CURR"))
    df.to_parquet(tmp_path / "features_A.parquet")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": {"features_A": {"sha256": fingerprint(df)}}}))
    assert check(tmp_path, manifest) == []
    assert load_stage("A", tmp_path, manifest).equals(df)
    df.assign(X=[1.0, 2.5]).to_parquet(tmp_path / "features_A.parquet")
    assert len(check(tmp_path, manifest)) == 1
    with pytest.raises(ValueError, match="differs"):
        load_stage("A", tmp_path, manifest)
