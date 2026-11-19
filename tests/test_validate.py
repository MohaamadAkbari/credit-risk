"""Data checks (credit_risk.data.validate) on a tiny hand-made release of all eight tables."""
import json

import pandas as pd
import pytest

from credit_risk.data.validate import check_rules, compare, profile, run


def _release(tmp_path, **changes):
    """Write a valid eight-table release, apply `changes` ({table: function(df) -> df}), return its folders."""
    tables = {
        "application_train": pd.DataFrame({"SK_ID_CURR": [1, 2, 3], "TARGET": [0, 1, 0],
                                           "EXT_SOURCE_1": [0.2, None, 0.9], "DAYS_BIRTH": [-9000, -12000, -20000],
                                           "FLAG_OWN_CAR": ["Y", "N", "N"], "REGION_RATING_CLIENT": [1, 2, 3]}),
        "application_test": pd.DataFrame({"SK_ID_CURR": [4], "EXT_SOURCE_1": [0.5], "DAYS_BIRTH": [-10000],
                                          "FLAG_OWN_CAR": ["N"], "REGION_RATING_CLIENT": [2]}),
        "bureau": pd.DataFrame({"SK_ID_CURR": [1, 1, 4], "SK_ID_BUREAU": [10, 11, 12],
                                "DAYS_CREDIT_UPDATE": [-5, 3, -1], "DAYS_CREDIT_ENDDATE": [400, -20, 365243]}),
        "bureau_balance": pd.DataFrame({"SK_ID_BUREAU": [10, 10], "MONTHS_BALANCE": [-1, 0]}),
        "previous_application": pd.DataFrame({"SK_ID_PREV": [20, 21], "SK_ID_CURR": [1, 2]}),
        "POS_CASH_balance": pd.DataFrame({"SK_ID_PREV": [20], "SK_ID_CURR": [1]}),
        "installments_payments": pd.DataFrame({"SK_ID_PREV": [20], "SK_ID_CURR": [1]}),
        "credit_card_balance": pd.DataFrame({"SK_ID_PREV": [21], "SK_ID_CURR": [2]}),
    }
    verdicts = {("bureau", "DAYS_CREDIT_UPDATE"): "ok_filter", ("bureau", "DAYS_CREDIT_ENDDATE"): "ok_planned"}
    interim = tmp_path / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, df in tables.items():
        if name != "application_test":
            rows += [{"table": name, "column": c, "verdict": verdicts.get((name, c), "ok")} for c in df.columns]
        df = changes.get(name, lambda d: d)(df.copy())
        df.to_parquet(interim / f"{name}.parquet", index=False)
    availability = tmp_path / "availability.csv"
    pd.DataFrame(rows).to_csv(availability, index=False)
    return interim, availability


def test_a_valid_release_passes_and_notes_the_filtered_rows(tmp_path):
    interim, availability = _release(tmp_path)
    fails, notes = check_rules(interim, availability)
    assert fails == []
    assert notes == ["bureau.DAYS_CREDIT_UPDATE: 1 rows dated after the application (dropped by the pipeline)"]


@pytest.mark.parametrize("table, change, expected", [
    ("application_train", lambda d: d.assign(SK_ID_CURR=[1, 1, 3]), "repeated keys"),
    ("application_train", lambda d: d.assign(TARGET=[0, 2, 0]), "TARGET"),
    ("application_train", lambda d: d.assign(EXT_SOURCE_1=[0.2, 1.5, 0.9]), "normalised score"),
    ("application_train", lambda d: d.assign(FLAG_OWN_CAR=["Y", "N", "yes"]), "flag levels"),
    ("application_train", lambda d: d.assign(DAYS_BIRTH=[-9000, -12000, 100]), "after the application"),
    ("application_train", lambda d: d.drop(columns="EXT_SOURCE_1"), "columns differ"),
    ("application_test", lambda d: d.assign(SK_ID_CURR=[3]), "both application_train and application_test"),
    ("bureau", lambda d: d.assign(SK_ID_CURR=[1, 1, 99]), "no known applicant"),
    ("bureau_balance", lambda d: d.assign(MONTHS_BALANCE=[-1, 2]), "after the application"),
])
def test_each_rule_catches_its_break(tmp_path, table, change, expected):
    interim, availability = _release(tmp_path, **{table: change})
    fails, _ = check_rules(interim, availability)
    assert any(expected in f for f in fails), fails


def test_profile_flags_a_different_release(tmp_path):
    interim, _ = _release(tmp_path)
    recorded = profile(interim, raw=None)
    assert compare(recorded, profile(interim, raw=None)) == []
    other, _ = _release(tmp_path / "other", application_train=lambda d: d.iloc[:2].assign(FLAG_OWN_CAR=["Y", "Z"]))
    diffs = compare(recorded, profile(other, raw=None))
    assert any("2 rows, recorded 3" in d for d in diffs)
    assert any("FLAG_OWN_CAR" in d for d in diffs)


def test_run_exits_one_on_any_failure(tmp_path, capsys):
    interim, availability = _release(tmp_path)
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps(profile(interim, raw=None)))
    assert run(interim, None, contract, availability) == 0
    bad, _ = _release(tmp_path / "bad", application_train=lambda d: d.assign(TARGET=[0, 2, 0]))
    assert run(bad, None, contract, availability) == 1
    assert "Rule failures (the data is wrong): 1" in capsys.readouterr().out
