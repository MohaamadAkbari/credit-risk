"""Fairness and slicing attributes. NOT model inputs: kept apart from the feature tables (D23).

Evaluation joins this table to predictions to report results by gender, age band, thin file and
product. It is the only module allowed to read protected columns, and it is not part of any stage.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from credit_risk.data.io import load

SOURCES = {"application_train": ["SK_ID_CURR", "CODE_GENDER", "DAYS_BIRTH", "NAME_CONTRACT_TYPE"],
           "bureau": ["SK_ID_CURR"]}
AGE_BANDS = [18, 25, 35, 45, 55, 65, 100]
AGE_LABELS = ["<25", "25-34", "35-44", "45-54", "55-64", "65+"]


def audit_table(app: pd.DataFrame, bureau_ids: pd.Series) -> pd.DataFrame:
    age = -app.DAYS_BIRTH / 365.25
    gender = app.CODE_GENDER.astype("object")
    return pd.DataFrame({
        "SK_ID_CURR": app.SK_ID_CURR.to_numpy(),
        "GENDER": gender.where(gender.isin(["F", "M"])).to_numpy(),
        "AGE": age.round(1).to_numpy(),
        "AGE_BAND": pd.cut(age, AGE_BANDS, right=False, labels=AGE_LABELS).astype("object").to_numpy(),
        "THIN_FILE": (~app.SK_ID_CURR.isin(bureau_ids)).to_numpy(),          # D30
        "CONTRACT_TYPE": app.NAME_CONTRACT_TYPE.astype("object").to_numpy(),
    }).set_index("SK_ID_CURR")


def build(interim: Path) -> pd.DataFrame:
    app = load(interim, "application_train", SOURCES["application_train"])
    ids = load(interim, "bureau", SOURCES["bureau"]).SK_ID_CURR.unique()
    return audit_table(app, pd.Series(ids))
