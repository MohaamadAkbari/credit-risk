"""Data-dictionary rules: column kinds, groups and readable ranges (credit_risk.data.dictionary)."""
import numpy as np
import pandas as pd

from credit_risk.data.dictionary import describe_range, group_of, kind_of


def test_kinds():
    assert kind_of("SK_ID_CURR", pd.Series([1, 2]), "key", "") == "key"
    assert kind_of("FLAG_OWN_CAR", pd.Series(["Y", "N"]), "ok", "") == "flag"
    assert kind_of("FLAG_PHONE", pd.Series([0, 1, 1]), "ok", "") == "flag"
    assert kind_of("NAME_INCOME_TYPE", pd.Series(["Working", "Pensioner"]), "ok", "") == "category"
    assert kind_of("DAYS_BIRTH", pd.Series([-10000.0, -20000.0]), "protected", "") == "days"
    assert kind_of("EXT_SOURCE_1", pd.Series([0.2, 0.7]), "review", "normalized") == "score"
    assert kind_of("AMT_CREDIT", pd.Series([1e5, 2e5]), "ok", "") == "amount"
    assert kind_of("AMT_REQ_CREDIT_BUREAU_YEAR", pd.Series([0.0, 3.0]), "ok", "") == "count"
    assert kind_of("HOUR_APPR_PROCESS_START", pd.Series([9.0, 14.0]), "exclude", "rounded") == "number"


def test_groups():
    assert group_of("application_train", "EXT_SOURCE_3") == "External scores"
    assert group_of("application_train", "APARTMENTS_MEDI") == "Building statistics"
    assert group_of("application_train", "REG_CITY_NOT_WORK_CITY") == "Region and address"
    assert group_of("bureau", "SK_ID_BUREAU") == "Identifiers"
    assert group_of("bureau", "AMT_CREDIT_SUM") == "Credits at other lenders"


def test_days_are_shown_as_years_low_to_high():
    s = pd.Series(-np.linspace(365.25 * 20, 365.25 * 60, 1001))
    text, stats = describe_range("days", s)
    assert text == "20.4-59.6 years (median 40.0)"           # 1st-99th percentile, low to high
    assert stats["max"] <= 0                      # raw values stay as stored (negative days)
