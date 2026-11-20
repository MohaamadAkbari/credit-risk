"""Main-table features: the application form (stage A) and its bureau-derived columns (stage B).

Seven main-table columns carry credit-bureau information (EXT_SOURCE_3 and the six
AMT_REQ_CREDIT_BUREAU_* enquiry counts): they are almost always missing when the applicant has no
bureau record. They enter at stage B with the bureau tables, so the A -> B ablation measures all
the bureau adds (D50). The leakage table records each column's stage.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from credit_risk.data.clean import clean_application
from credit_risk.data.io import load
from credit_risk.paths import AVAILABILITY

NOT_FEATURES = {"key", "label", "protected", "exclude"}
# Near-constant flags (fewer than 100 rows differ) carry no signal.
NEAR_CONSTANT = ["FLAG_MOBIL", "FLAG_DOCUMENT_2", "FLAG_DOCUMENT_4", "FLAG_DOCUMENT_7",
                 "FLAG_DOCUMENT_10", "FLAG_DOCUMENT_12", "FLAG_DOCUMENT_17"]
# Exact or near-exact duplicates (D52): FLAG_EMP_PHONE = 1 - EMPLOYED_NA in all but 12 rows;
# OBS_60 correlates 0.998 with OBS_30.
DUPLICATES = ["FLAG_EMP_PHONE", "OBS_60_CNT_SOCIAL_CIRCLE"]
# Building statistics come in three versions of one quantity: _MEDI and numeric _MODE correlate
# 0.99+ and 0.97+ with _AVG and share its missing pattern (checked 18 Nov 2026). Keep _AVG
# and the text-valued _MODE columns, which have no _AVG twin.
DUPLICATE_SUFFIXES = ("_MEDI",)
NUMERIC_MODE_DUPLICATES = True
EXT_A = ["EXT_SOURCE_1", "EXT_SOURCE_2"]
EXT_ALL = [*EXT_A, "EXT_SOURCE_3"]


def allowed_columns(availability: Path = AVAILABILITY, stage: str = "A") -> list[str]:
    """Main-table columns the leakage table allows at this stage, minus the deliberate drops above."""
    t = pd.read_csv(availability)
    t = t[(t.table == "application_train") & ~t.verdict.isin(NOT_FEATURES) & (t.stage == stage)]
    drop = set(NEAR_CONSTANT) | set(DUPLICATES)
    cols = [c for c in t.column if c not in drop and not c.endswith(DUPLICATE_SUFFIXES)]
    if NUMERIC_MODE_DUPLICATES:
        numeric_mode = set(t[(t["min"].notna()) & t.column.str.endswith("_MODE")].column) - {"TOTALAREA_MODE"}
        cols = [c for c in cols if c not in numeric_mode]
    return cols


def sources(availability: Path = AVAILABILITY) -> dict[str, list[str]]:
    return {"application_train": ["SK_ID_CURR", *allowed_columns(availability)]}


def bureau_sources(availability: Path = AVAILABILITY) -> dict[str, list[str]]:
    """Stage B part: the bureau-derived main-table columns plus EXT_SOURCE_1/2 for the combined scores."""
    return {"application_train": ["SK_ID_CURR", *allowed_columns(availability, stage="B"), *EXT_A]}


def features(app: pd.DataFrame) -> pd.DataFrame:
    """Stage A block."""
    x = clean_application(app)
    x["CREDIT_INCOME"] = x.AMT_CREDIT / x.AMT_INCOME_TOTAL
    x["ANNUITY_INCOME"] = x.AMT_ANNUITY / x.AMT_INCOME_TOTAL
    x["CREDIT_GOODS"] = x.AMT_CREDIT / x.AMT_GOODS_PRICE
    x["CREDIT_TERM"] = x.AMT_CREDIT / x.AMT_ANNUITY                      # roughly the term in months
    x["INCOME_PER_PERSON"] = x.AMT_INCOME_TOTAL / x.CNT_FAM_MEMBERS
    ext = x[[c for c in EXT_A if c in x]]
    x["EXT_SOURCE_12_MEAN"] = ext.mean(axis=1)
    x["EXT_SOURCE_12_MIN"] = ext.min(axis=1)
    docs = [c for c in x.columns if c.startswith("FLAG_DOCUMENT_")]
    x["DOCUMENT_COUNT"] = x[docs].sum(axis=1)
    return x.set_index("SK_ID_CURR")


def bureau_features(app: pd.DataFrame) -> pd.DataFrame:
    """Stage B block: bureau-derived columns as they are, plus scores combined over all three sources."""
    x = app.set_index("SK_ID_CURR")
    ext = x[EXT_ALL]
    out = x.drop(columns=EXT_A)
    out["EXT_SOURCE_MEAN"] = ext.mean(axis=1)
    out["EXT_SOURCE_MIN"] = ext.min(axis=1)
    out["EXT_SOURCE_COUNT"] = ext.notna().sum(axis=1).astype("int8")
    return out


def build(interim: Path, availability: Path = AVAILABILITY) -> pd.DataFrame:
    return features(load(interim, "application_train", sources(availability)["application_train"]))


def build_bureau(interim: Path, availability: Path = AVAILABILITY) -> pd.DataFrame:
    return bureau_features(load(interim, "application_train", bureau_sources(availability)["application_train"]))
