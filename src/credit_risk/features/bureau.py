"""Stage B: credits at other lenders (bureau) and their monthly status (bureau_balance)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_risk.data.clean import clean_bureau, clean_bureau_balance
from credit_risk.data.io import load

SOURCES = {
    "bureau": ["SK_ID_CURR", "SK_ID_BUREAU", "CREDIT_ACTIVE", "CREDIT_CURRENCY", "DAYS_CREDIT",
               "CREDIT_DAY_OVERDUE", "DAYS_CREDIT_ENDDATE", "DAYS_ENDDATE_FACT", "AMT_CREDIT_MAX_OVERDUE",
               "CNT_CREDIT_PROLONG", "AMT_CREDIT_SUM", "AMT_CREDIT_SUM_DEBT", "AMT_CREDIT_SUM_OVERDUE",
               "CREDIT_TYPE", "DAYS_CREDIT_UPDATE", "AMT_ANNUITY"],
    "bureau_balance": ["SK_ID_BUREAU", "MONTHS_BALANCE", "STATUS"],
}
# C = closed and X = unknown carry no days-past-due information; 1..5 are DPD buckets.
STATUS_DPD = {"C": 0.0, "0": 0.0, "1": 1.0, "2": 2.0, "3": 3.0, "4": 4.0, "5": 5.0, "X": np.nan}


def bureau_features(bu: pd.DataFrame) -> pd.DataFrame:
    b = clean_bureau(bu)
    active = b.CREDIT_ACTIVE == "Active"
    main_ccy = b.CREDIT_CURRENCY == "currency 1"           # amounts in other currencies are not comparable
    b = b.assign(
        ACTIVE=active.astype("int8"),
        BAD=b.CREDIT_ACTIVE.isin(["Bad debt", "Sold"]).astype("int8"),
        OPENED_7D=(b.DAYS_CREDIT >= -7).astype("int8"),
        OPENED_90D=(b.DAYS_CREDIT >= -90).astype("int8"),
        OVERDUE_NOW=(b.CREDIT_DAY_OVERDUE > 0).astype("int8"),
        CARD=(b.CREDIT_TYPE == "Credit card").astype("int8"),
        MICRO=(b.CREDIT_TYPE == "Microloan").astype("int8"),
        ACT_DEBT=b.AMT_CREDIT_SUM_DEBT.clip(lower=0).where(active & main_ccy),
        ACT_CREDIT=b.AMT_CREDIT_SUM.where(active & main_ccy),
        ACT_ANNUITY=b.AMT_ANNUITY.where(active & main_ccy),
        OVERDUE_AMT=b.AMT_CREDIT_SUM_OVERDUE.where(main_ccy),
        ACT_END=b.DAYS_CREDIT_ENDDATE.where(active),
    )
    g = b.groupby("SK_ID_CURR")
    out = g.agg(BUR_COUNT=("SK_ID_BUREAU", "size"), BUR_ACTIVE_COUNT=("ACTIVE", "sum"),
                BUR_BAD_OR_SOLD_COUNT=("BAD", "sum"), BUR_OPENED_7D_COUNT=("OPENED_7D", "sum"),
                BUR_OPENED_90D_COUNT=("OPENED_90D", "sum"), BUR_DAYS_CREDIT_MAX=("DAYS_CREDIT", "max"),
                BUR_DAYS_CREDIT_MIN=("DAYS_CREDIT", "min"), BUR_OVERDUE_NOW_COUNT=("OVERDUE_NOW", "sum"),
                BUR_DAY_OVERDUE_MAX=("CREDIT_DAY_OVERDUE", "max"), BUR_AMT_OVERDUE_SUM=("OVERDUE_AMT", "sum"),
                BUR_MAX_OVERDUE_MAX=("AMT_CREDIT_MAX_OVERDUE", "max"), BUR_PROLONG_SUM=("CNT_CREDIT_PROLONG", "sum"),
                BUR_ACTIVE_DEBT_SUM=("ACT_DEBT", "sum"), BUR_ACTIVE_CREDIT_SUM=("ACT_CREDIT", "sum"),
                BUR_ACTIVE_ANNUITY_SUM=("ACT_ANNUITY", "sum"), BUR_ACTIVE_END_MAX=("ACT_END", "max"),
                BUR_CARD_COUNT=("CARD", "sum"), BUR_MICROLOAN_COUNT=("MICRO", "sum"))
    out["BUR_ACTIVE_DEBT_RATIO"] = out.BUR_ACTIVE_DEBT_SUM / out.BUR_ACTIVE_CREDIT_SUM.replace(0, np.nan)
    return out


def balance_features(bb: pd.DataFrame, bu_keys: pd.DataFrame, max_month: int = 0) -> pd.DataFrame:
    """Worst days-past-due bucket ever and in the last 12 months, and the share of late months."""
    m = clean_bureau_balance(bb, max_month)
    dpd = m.STATUS.astype("object").map(STATUS_DPD).astype("float32")
    m = pd.DataFrame({"SK_ID_BUREAU": m.SK_ID_BUREAU.to_numpy(), "DPD": dpd.to_numpy(),
                      "DPD_12M": dpd.where(m.MONTHS_BALANCE >= -12).to_numpy(),
                      "LATE": (dpd >= 1).astype("float32").where(dpd.notna()).to_numpy()})
    per_credit = m.groupby("SK_ID_BUREAU").agg(WORST=("DPD", "max"), WORST_12M=("DPD_12M", "max"),
                                               LATE_SHARE=("LATE", "mean"), MONTHS=("DPD", "size"))
    j = bu_keys.merge(per_credit, left_on="SK_ID_BUREAU", right_index=True, how="inner")
    return j.groupby("SK_ID_CURR").agg(BB_WORST_DPD_MAX=("WORST", "max"), BB_WORST_DPD_12M_MAX=("WORST_12M", "max"),
                                        BB_LATE_SHARE_MEAN=("LATE_SHARE", "mean"), BB_MONTHS_COUNT=("MONTHS", "sum"))


def build(interim: Path, max_month: int = 0) -> pd.DataFrame:
    bu = load(interim, "bureau", SOURCES["bureau"])
    out = bureau_features(bu)
    keys = clean_bureau(bu)[["SK_ID_CURR", "SK_ID_BUREAU"]]
    del bu
    bb = load(interim, "bureau_balance", SOURCES["bureau_balance"])
    return out.join(balance_features(bb, keys, max_month), how="left")
