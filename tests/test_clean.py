"""Cleaning rules from reports/leakage_table.md, each checked on a tiny hand-made table."""
import numpy as np
import pandas as pd

from credit_risk.data.clean import (
    clean_application,
    clean_bureau,
    clean_bureau_balance,
    clean_installments,
    clean_previous,
)


def test_application_recodes_employment_marker_and_xna_gender():
    app = pd.DataFrame({"DAYS_EMPLOYED": [-100.0, 365243.0], "CODE_GENDER": ["F", "XNA"]})
    out = clean_application(app)
    assert out.DAYS_EMPLOYED.isna().tolist() == [False, True]
    assert out.EMPLOYED_NA.tolist() == [0, 1]
    assert out.CODE_GENDER.isna().tolist() == [False, True]


def test_bureau_drops_rows_updated_after_application_and_nulls_impossible_dates():
    bu = pd.DataFrame({"DAYS_CREDIT": [-500.0, -300.0, -200.0, -100.0],
                       "DAYS_CREDIT_UPDATE": [-10.0, 30.0, -5.0, -1.0],     # second row: after the application
                       "DAYS_CREDIT_ENDDATE": [200.0, 100.0, -41000.0, 50.0],  # planned dates stay
                       "DAYS_ENDDATE_FACT": [-400.0, np.nan, np.nan, -150.0]})  # last row ends before it starts
    out = clean_bureau(bu)
    assert len(out) == 3
    assert out.DAYS_CREDIT_ENDDATE.tolist()[0] == 200.0
    assert np.isnan(out.DAYS_CREDIT_ENDDATE.iloc[1])
    assert np.isnan(out.DAYS_ENDDATE_FACT.iloc[2])


def test_bureau_balance_month_zero_is_optional():
    bb = pd.DataFrame({"MONTHS_BALANCE": [-2, -1, 0]})
    assert len(clean_bureau_balance(bb, 0)) == 3
    assert len(clean_bureau_balance(bb, -1)) == 2


def test_previous_recodes_markers_and_keeps_amounts_of_approved_only():
    p = pd.DataFrame({"DAYS_LAST_DUE": [365243.0, -20.0], "SELLERPLACE_AREA": [-1.0, 50.0],
                      "AMT_CREDIT": [1000.0, 0.0], "NAME_CONTRACT_STATUS": ["Approved", "Refused"],
                      "AMT_DOWN_PAYMENT": [-0.5, 10.0]})
    out = clean_previous(p)
    assert out.DAYS_LAST_DUE.isna().tolist() == [True, False]
    assert out.SELLERPLACE_AREA.isna().tolist() == [True, False]
    assert out.AMT_CREDIT.isna().tolist() == [False, True]
    assert out.AMT_DOWN_PAYMENT.tolist() == [0.0, 10.0]


def test_installments_sum_split_payments_before_measuring_lateness():
    rows = [  # one instalment due on day -100, paid in two parts on days -105 and -95
        (1, 10, 1, 1, -100.0, -105.0, 500.0, 300.0),
        (1, 10, 1, 1, -100.0, -95.0, 500.0, 200.0),
        (1, 10, 1, 2, -70.0, np.nan, 500.0, np.nan),     # never paid
        (1, 10, 1, 3, -40.0, -900.0, 500.0, 500.0),      # paid absurdly early: capped
    ]
    cols = ["SK_ID_CURR", "SK_ID_PREV", "NUM_INSTALMENT_VERSION", "NUM_INSTALMENT_NUMBER", "DAYS_INSTALMENT",
            "DAYS_ENTRY_PAYMENT", "AMT_INSTALMENT", "AMT_PAYMENT"]
    out = clean_installments(pd.DataFrame(rows, columns=cols)).sort_values("NUM_INSTALMENT_NUMBER")
    assert len(out) == 3
    first = out.iloc[0]
    assert first.AMT_PAYMENT == 500.0 and first.DAYS_LATE == 5.0     # fully paid, 5 days late
    assert np.isnan(out.iloc[1].AMT_PAYMENT)
    assert out.iloc[2].DAYS_LATE == -365
