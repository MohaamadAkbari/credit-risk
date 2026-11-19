"""Each aggregation on a tiny table with a known answer."""
import numpy as np
import pandas as pd
import pytest

from credit_risk.features import bureau, installments, monthly, previous
from credit_risk.features.application import features as app_features


def test_application_ratios():
    app = pd.DataFrame({"SK_ID_CURR": [1], "AMT_CREDIT": [200.0], "AMT_INCOME_TOTAL": [100.0],
                        "AMT_ANNUITY": [10.0], "AMT_GOODS_PRICE": [160.0], "CNT_FAM_MEMBERS": [2.0],
                        "EXT_SOURCE_1": [np.nan], "EXT_SOURCE_2": [0.2], "EXT_SOURCE_3": [0.6],
                        "DAYS_EMPLOYED": [365243.0], "FLAG_DOCUMENT_3": [1], "FLAG_DOCUMENT_8": [1]})
    r = app_features(app).loc[1]
    assert r.CREDIT_INCOME == 2 and r.ANNUITY_INCOME == 0.1 and r.CREDIT_GOODS == 1.25 and r.CREDIT_TERM == 20
    assert r.INCOME_PER_PERSON == 50
    assert r.EXT_SOURCE_MEAN == pytest.approx(0.4) and r.EXT_SOURCE_MIN == 0.2 and r.EXT_SOURCE_COUNT == 2
    assert r.DOCUMENT_COUNT == 2 and r.EMPLOYED_NA == 1 and np.isnan(r.DAYS_EMPLOYED)


def _bureau():
    return pd.DataFrame({
        "SK_ID_CURR": [1, 1, 1, 2], "SK_ID_BUREAU": [11, 12, 13, 21],
        "CREDIT_ACTIVE": ["Active", "Closed", "Active", "Closed"],
        "CREDIT_CURRENCY": ["currency 1", "currency 1", "currency 2", "currency 1"],
        "DAYS_CREDIT": [-5.0, -800.0, -100.0, -50.0], "CREDIT_DAY_OVERDUE": [10.0, 0.0, 0.0, 0.0],
        "DAYS_CREDIT_ENDDATE": [300.0, -400.0, 100.0, -10.0], "DAYS_ENDDATE_FACT": [np.nan, -400.0, np.nan, -10.0],
        "AMT_CREDIT_MAX_OVERDUE": [50.0, 0.0, np.nan, 0.0], "CNT_CREDIT_PROLONG": [0, 1, 0, 0],
        "AMT_CREDIT_SUM": [1000.0, 500.0, 9999.0, 300.0], "AMT_CREDIT_SUM_DEBT": [400.0, 0.0, 9999.0, 0.0],
        "AMT_CREDIT_SUM_OVERDUE": [20.0, 0.0, 0.0, 0.0], "CREDIT_TYPE": ["Consumer credit", "Credit card", "Car loan", "Microloan"],
        "DAYS_CREDIT_UPDATE": [-1.0, -300.0, -2.0, 40.0], "AMT_ANNUITY": [50.0, np.nan, 999.0, np.nan]})


def test_bureau_counts_amounts_and_post_application_row_dropped():
    out = bureau.bureau_features(_bureau())
    a = out.loc[1]
    assert a.BUR_COUNT == 3 and a.BUR_ACTIVE_COUNT == 2 and a.BUR_OPENED_7D_COUNT == 1
    assert a.BUR_OVERDUE_NOW_COUNT == 1 and a.BUR_CARD_COUNT == 1
    assert a.BUR_ACTIVE_DEBT_SUM == 400 and a.BUR_ACTIVE_CREDIT_SUM == 1000     # currency 2 excluded
    assert a.BUR_ACTIVE_DEBT_RATIO == pytest.approx(0.4) and a.BUR_ACTIVE_END_MAX == 300
    assert 2 not in out.index                       # its only row was updated after the application


def test_bureau_balance_worst_status_and_month_zero_ablation():
    bb = pd.DataFrame({"SK_ID_BUREAU": [11, 11, 11, 11, 12],
                       "MONTHS_BALANCE": [-30, -5, -1, 0, -2], "STATUS": ["2", "0", "X", "5", "C"]})
    keys = pd.DataFrame({"SK_ID_CURR": [1, 1], "SK_ID_BUREAU": [11, 12]})
    with_0 = bureau.balance_features(bb, keys, 0).loc[1]
    without_0 = bureau.balance_features(bb, keys, -1).loc[1]
    assert with_0.BB_WORST_DPD_MAX == 5 and with_0.BB_WORST_DPD_12M_MAX == 5
    assert without_0.BB_WORST_DPD_MAX == 2 and without_0.BB_WORST_DPD_12M_MAX == 0


def test_previous_refusals_and_running_loans():
    p = pd.DataFrame({"SK_ID_CURR": [1, 1, 1, 1],
                      "NAME_CONTRACT_STATUS": ["Approved", "Refused", "Refused", "Canceled"],
                      "AMT_APPLICATION": [1100.0, 500.0, 0.0, 0.0], "AMT_CREDIT": [1000.0, 0.0, 0.0, 0.0],
                      "AMT_ANNUITY": [100.0, np.nan, np.nan, np.nan], "CNT_PAYMENT": [12.0, np.nan, np.nan, np.nan],
                      "DAYS_DECISION": [-400.0, -20.0, -200.0, -10.0], "CODE_REJECT_REASON": ["XAP", "HC", "SCO", "XAP"],
                      "NAME_YIELD_GROUP": ["high", "XNA", "XNA", "XNA"],
                      "DAYS_LAST_DUE": [365243.0, np.nan, np.nan, np.nan], "DAYS_LAST_DUE_1ST_VERSION": [200.0, np.nan, np.nan, np.nan]})
    r = previous.features(p).loc[1]
    assert r.PREV_COUNT == 4 and r.PREV_REFUSED_COUNT == 2 and r.PREV_REFUSED_SHARE == 0.5
    assert r.PREV_LAST_REFUSAL_DAYS == -20 and r.PREV_APPLIED_30D_COUNT == 2
    assert r.PREV_APPROVED_CREDIT_MEAN == 1000 and r.PREV_ASKED_VS_GRANTED_MEAN == pytest.approx(1.1)
    assert r.PREV_RUNNING_COUNT == 1 and r.PREV_RUNNING_ANNUITY_SUM == 100
    assert r.PREV_REJECT_HC_COUNT == 1 and r.PREV_REJECT_SCO_COUNT == 1


def test_installment_lateness_shares():
    cols = ["SK_ID_CURR", "SK_ID_PREV", "NUM_INSTALMENT_VERSION", "NUM_INSTALMENT_NUMBER", "DAYS_INSTALMENT",
            "DAYS_ENTRY_PAYMENT", "AMT_INSTALMENT", "AMT_PAYMENT"]
    rows = [(1, 9, 1, 1, -500.0, -490.0, 100.0, 100.0),    # 10 days late
            (1, 9, 1, 2, -470.0, -475.0, 100.0, 60.0),     # early but under-paid
            (1, 9, 1, 3, -30.0, -30.0, 100.0, 100.0),      # on time, within the last year
            (1, 9, 1, 4, -10.0, np.nan, 100.0, np.nan)]    # unpaid
    r = installments.features(pd.DataFrame(rows, columns=cols)).loc[1]
    assert r.INST_COUNT == 4 and r.INST_UNPAID_COUNT == 1
    assert r.INST_LATE_SHARE == pytest.approx(1 / 3) and r.INST_LATE_SHARE_1Y == 0
    assert r.INST_LATE_DAYS_MAX == 10 and r.INST_UNDERPAID_SHARE == 0.5


def test_pos_and_card_latest_month():
    pos = pd.DataFrame({"SK_ID_CURR": [1, 1, 1], "SK_ID_PREV": [5, 5, 6], "MONTHS_BALANCE": [-20, -2, -3],
                        "CNT_INSTALMENT_FUTURE": [10.0, 4.0, 0.0], "NAME_CONTRACT_STATUS": ["Active", "Active", "Completed"],
                        "SK_DPD": [30.0, 0.0, 0.0], "SK_DPD_DEF": [30.0, 0.0, 0.0]})
    r = monthly.pos_features(pos).loc[1]
    assert r.POS_LOAN_COUNT == 2 and r.POS_DPD_MAX == 30 and r.POS_DPD_12M_MAX == 0
    assert r.POS_REMAINING_INSTALMENTS_SUM == 4
    cc = pd.DataFrame({"SK_ID_CURR": [1, 1], "SK_ID_PREV": [7, 7], "MONTHS_BALANCE": [-2, -1],
                       "AMT_BALANCE": [500.0, 900.0], "AMT_CREDIT_LIMIT_ACTUAL": [1000.0, 1000.0],
                       "AMT_DRAWINGS_CURRENT": [0.0, 400.0], "AMT_PAYMENT_TOTAL_CURRENT": [50.0, 10.0],
                       "AMT_INST_MIN_REGULARITY": [40.0, 45.0], "SK_DPD": [0.0, 0.0], "SK_DPD_DEF": [0.0, 0.0]})
    c = monthly.cc_features(cc).loc[1]
    assert c.CC_UTIL_MEAN == pytest.approx(0.7) and c.CC_UTIL_LATEST_MEAN == pytest.approx(0.9)
    assert c.CC_PAID_BELOW_MIN_SHARE == 0.5 and c.CC_BALANCE_LATEST_SUM == 900
