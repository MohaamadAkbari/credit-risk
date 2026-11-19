"""The leakage guard: every column a feature module reads must be allowed by the leakage table."""
from pathlib import Path

import pandas as pd
import pytest

from credit_risk.features import application, bureau, installments, monthly, previous
from credit_risk.features.build import STAGES

AVAIL = Path(__file__).resolve().parents[1] / "configs" / "feature_availability.csv"
FORBIDDEN = {"label", "protected"}
STAGE_RANK = {"A": 0, "B": 1, "C": 2}
MODULES = {"application": (application.sources(AVAIL), "A"), "bureau": (bureau.SOURCES, "B"),
           "previous": (previous.SOURCES, "C"), "installments": (installments.SOURCES, "C"),
           "monthly": (monthly.SOURCES, "C")}


@pytest.fixture(scope="module")
def verdicts():
    t = pd.read_csv(AVAIL)
    return {(r.table, r.column): (r.verdict, r.stage) for r in t.itertuples()}


@pytest.mark.parametrize("name", MODULES)
def test_declared_columns_are_allowed(name, verdicts):
    sources, stage = MODULES[name]
    for table, cols in sources.items():
        for c in cols:
            assert (table, c) in verdicts, f"{name} reads {table}.{c}, which is not in the leakage table"
            verdict, col_stage = verdicts[(table, c)]
            assert verdict not in FORBIDDEN, f"{name} reads {table}.{c} ({verdict})"
            if verdict == "key":
                assert c.startswith("SK_ID_"), c
            else:
                assert STAGE_RANK[col_stage] <= STAGE_RANK[stage], f"{table}.{c} is stage {col_stage}, used in {stage}"


def test_application_features_exclude_label_and_protected():
    cols = set(application.allowed_columns(AVAIL))
    assert not cols & {"TARGET", "CODE_GENDER", "DAYS_BIRTH", "SK_ID_CURR"}
    assert "FLAG_MOBIL" not in cols and not any(c.endswith("_MEDI") for c in cols)


def test_audit_table_is_not_a_stage():
    assert all("audit" not in blocks for blocks in STAGES.values())
