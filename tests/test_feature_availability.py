"""Checks on the leakage table, configs/feature_availability.csv.

The table is generated from the data (make leakage) but committed, so these tests run without
the data. They guard the rules the feature pipeline relies on.
"""
from pathlib import Path

import pandas as pd
import pytest

from credit_risk.data.availability import VERDICTS

CSV = Path(__file__).resolve().parents[1] / "configs" / "feature_availability.csv"
NOT_FEATURES = {"key", "label", "protected", "exclude"}


@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    return pd.read_csv(CSV)


def test_one_row_per_column(table):
    assert not table.duplicated(["table", "column"]).any()


def test_all_seven_training_tables_covered(table):
    assert table.groupby("table").size().to_dict() == {
        "application_train": 122, "bureau": 17, "bureau_balance": 3, "previous_application": 37,
        "POS_CASH_balance": 8, "installments_payments": 8, "credit_card_balance": 23}


def test_verdicts_are_known(table):
    assert set(table.verdict) <= set(VERDICTS)


def test_label_and_protected_attributes_never_enter_the_model(table):
    app = table[table.table == "application_train"].set_index("column")
    assert app.loc["TARGET", "verdict"] == "label"
    assert app.loc["CODE_GENDER", "verdict"] == "protected"
    assert app.loc["DAYS_BIRTH", "verdict"] == "protected"
    assert (table.loc[table.verdict.isin(NOT_FEATURES), "stage"] == "-").all()


def test_feature_columns_have_an_ablation_stage(table):
    feats = table[~table.verdict.isin(NOT_FEATURES)]
    assert set(feats.stage) <= {"A", "B", "C"}
    app = feats[feats.table == "application_train"].set_index("column").stage
    bureau_derived = {"EXT_SOURCE_3", *[f"AMT_REQ_CREDIT_BUREAU_{p}" for p in ("HOUR", "DAY", "WEEK", "MON", "QRT", "YEAR")]}
    assert set(app[app == "B"].index) == bureau_derived          # D50
    assert set(app[app != "B"]) == {"A"}


def test_process_fields_are_excluded(table):
    app = table[table.table == "application_train"].set_index("column")
    assert app.loc["HOUR_APPR_PROCESS_START", "verdict"] == "exclude"           # D51
    assert app.loc["WEEKDAY_APPR_PROCESS_START", "verdict"] == "exclude"


def test_dates_after_the_application_are_explained(table):
    """A positive relative date is allowed only for planned dates or rows that get filtered out."""
    after = table[pd.to_numeric(table.n_after_application, errors="coerce").fillna(0) > 0]
    assert set(after.verdict) <= {"ok_planned", "ok_filter"}
    assert set(zip(after.table, after.column, strict=True)) == {
        ("bureau", "DAYS_CREDIT_ENDDATE"), ("bureau", "DAYS_CREDIT_UPDATE"),
        ("previous_application", "DAYS_LAST_DUE_1ST_VERSION")}
