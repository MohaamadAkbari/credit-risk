"""Stage C: monthly snapshots of earlier POS / cash loans and credit cards."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_risk.data.io import load

POS_SOURCES = {"POS_CASH_balance": ["SK_ID_CURR", "SK_ID_PREV", "MONTHS_BALANCE", "CNT_INSTALMENT_FUTURE",
                                    "NAME_CONTRACT_STATUS", "SK_DPD", "SK_DPD_DEF"]}
CC_SOURCES = {"credit_card_balance": ["SK_ID_CURR", "SK_ID_PREV", "MONTHS_BALANCE", "AMT_BALANCE",
                                      "AMT_CREDIT_LIMIT_ACTUAL", "AMT_DRAWINGS_CURRENT", "AMT_PAYMENT_TOTAL_CURRENT",
                                      "AMT_INST_MIN_REGULARITY", "SK_DPD", "SK_DPD_DEF"]}
SOURCES = {**POS_SOURCES, **CC_SOURCES}


def _latest(df: pd.DataFrame) -> pd.DataFrame:
    """The most recent month of each loan or card."""
    return df.sort_values("MONTHS_BALANCE").drop_duplicates("SK_ID_PREV", keep="last")


def pos_features(pos: pd.DataFrame) -> pd.DataFrame:
    p = pos.assign(DPD_DEF=(pos.SK_DPD_DEF > 0).astype("int8"),
                   DPD_12M=pos.SK_DPD.where(pos.MONTHS_BALANCE >= -12))
    out = p.groupby("SK_ID_CURR").agg(POS_MONTHS_COUNT=("SK_ID_PREV", "size"), POS_LOAN_COUNT=("SK_ID_PREV", "nunique"),
                                      POS_DPD_MAX=("SK_DPD", "max"), POS_DPD_12M_MAX=("DPD_12M", "max"),
                                      POS_DPD_DEF_SHARE=("DPD_DEF", "mean"))
    last = _latest(p)
    active = last[last.NAME_CONTRACT_STATUS.astype("object") == "Active"]
    out["POS_REMAINING_INSTALMENTS_SUM"] = active.groupby("SK_ID_CURR").CNT_INSTALMENT_FUTURE.sum()
    return out


def cc_features(cc: pd.DataFrame) -> pd.DataFrame:
    limit = cc.AMT_CREDIT_LIMIT_ACTUAL.where(cc.AMT_CREDIT_LIMIT_ACTUAL > 0)
    c = cc.assign(UTIL=cc.AMT_BALANCE / limit, DPD_DEF=(cc.SK_DPD_DEF > 0).astype("int8"),
                  BELOW_MIN=((cc.AMT_INST_MIN_REGULARITY > 0) &
                             (cc.AMT_PAYMENT_TOTAL_CURRENT < cc.AMT_INST_MIN_REGULARITY)).astype("int8"))
    out = c.groupby("SK_ID_CURR").agg(CC_MONTHS_COUNT=("SK_ID_PREV", "size"), CC_CARD_COUNT=("SK_ID_PREV", "nunique"),
                                      CC_UTIL_MEAN=("UTIL", "mean"), CC_DRAWINGS_MEAN=("AMT_DRAWINGS_CURRENT", "mean"),
                                      CC_DPD_MAX=("SK_DPD", "max"), CC_DPD_DEF_SHARE=("DPD_DEF", "mean"),
                                      CC_PAID_BELOW_MIN_SHARE=("BELOW_MIN", "mean"))
    last = _latest(c)
    g = last.groupby("SK_ID_CURR")
    out["CC_UTIL_LATEST_MEAN"] = g.UTIL.mean()
    out["CC_BALANCE_LATEST_SUM"] = g.AMT_BALANCE.sum()
    out["CC_LIMIT_LATEST_SUM"] = g.AMT_CREDIT_LIMIT_ACTUAL.sum()
    out.replace([np.inf, -np.inf], np.nan, inplace=True)
    return out


def build_pos(interim: Path) -> pd.DataFrame:
    return pos_features(load(interim, "POS_CASH_balance", POS_SOURCES["POS_CASH_balance"]))


def build_cc(interim: Path) -> pd.DataFrame:
    return cc_features(load(interim, "credit_card_balance", CC_SOURCES["credit_card_balance"]))
