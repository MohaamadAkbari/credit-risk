"""Stage A: application-form features."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from credit_risk.data.clean import clean_application
from credit_risk.data.io import load
from credit_risk.paths import AVAILABILITY

NOT_FEATURES = {"key", "label", "protected"}
# Near-constant flags (fewer than 100 rows differ) carry no signal.
NEAR_CONSTANT = ["FLAG_MOBIL", "FLAG_DOCUMENT_2", "FLAG_DOCUMENT_4", "FLAG_DOCUMENT_7",
                 "FLAG_DOCUMENT_10", "FLAG_DOCUMENT_12", "FLAG_DOCUMENT_17"]
# Building statistics come in three versions of one quantity: _MEDI and numeric _MODE correlate
# 0.99+ and 0.97+ with _AVG and share its missing pattern (checked 18 Nov 2026). Keep _AVG
# and the text-valued _MODE columns, which have no _AVG twin.
DUPLICATE_SUFFIXES = ("_MEDI",)
NUMERIC_MODE_DUPLICATES = True


def allowed_columns(availability: Path = AVAILABILITY) -> list[str]:
    """Main-table columns the leakage table allows, minus the deliberate drops above."""
    t = pd.read_csv(availability)
    t = t[(t.table == "application_train") & ~t.verdict.isin(NOT_FEATURES)]
    cols = [c for c in t.column if c not in NEAR_CONSTANT and not c.endswith(DUPLICATE_SUFFIXES)]
    if NUMERIC_MODE_DUPLICATES:
        numeric_mode = set(t[(t["min"].notna()) & t.column.str.endswith("_MODE")].column) - {"TOTALAREA_MODE"}
        cols = [c for c in cols if c not in numeric_mode]
    return cols


def sources(availability: Path = AVAILABILITY) -> dict[str, list[str]]:
    return {"application_train": ["SK_ID_CURR", *allowed_columns(availability)]}


def features(app: pd.DataFrame) -> pd.DataFrame:
    x = clean_application(app)
    x["CREDIT_INCOME"] = x.AMT_CREDIT / x.AMT_INCOME_TOTAL
    x["ANNUITY_INCOME"] = x.AMT_ANNUITY / x.AMT_INCOME_TOTAL
    x["CREDIT_GOODS"] = x.AMT_CREDIT / x.AMT_GOODS_PRICE
    x["CREDIT_TERM"] = x.AMT_CREDIT / x.AMT_ANNUITY                      # roughly the term in months
    x["INCOME_PER_PERSON"] = x.AMT_INCOME_TOTAL / x.CNT_FAM_MEMBERS
    ext = x[["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]]
    x["EXT_SOURCE_MEAN"] = ext.mean(axis=1)
    x["EXT_SOURCE_MIN"] = ext.min(axis=1)
    x["EXT_SOURCE_COUNT"] = ext.notna().sum(axis=1).astype("int8")
    docs = [c for c in x.columns if c.startswith("FLAG_DOCUMENT_")]
    x["DOCUMENT_COUNT"] = x[docs].sum(axis=1)
    return x.set_index("SK_ID_CURR")


def build(interim: Path, availability: Path = AVAILABILITY) -> pd.DataFrame:
    src = sources(availability)["application_train"]
    return features(load(interim, "application_train", src))
