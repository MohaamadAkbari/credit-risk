"""Stage C: earlier applications to Home Credit."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_risk.data.clean import clean_previous
from credit_risk.data.io import load

SOURCES = {"previous_application": [
    "SK_ID_CURR", "NAME_CONTRACT_STATUS", "AMT_APPLICATION", "AMT_CREDIT", "AMT_ANNUITY", "CNT_PAYMENT",
    "DAYS_DECISION", "CODE_REJECT_REASON", "NAME_YIELD_GROUP", "DAYS_LAST_DUE", "DAYS_LAST_DUE_1ST_VERSION"]}


def features(prev: pd.DataFrame) -> pd.DataFrame:
    p = clean_previous(prev)
    st = p.NAME_CONTRACT_STATUS.astype("object")
    approved, refused = st == "Approved", st == "Refused"
    # Still running: approved, real last due date not reached yet, planned end in the future.
    running = approved & p.DAYS_LAST_DUE.isna() & (p.DAYS_LAST_DUE_1ST_VERSION > 0)
    reason = p.CODE_REJECT_REASON.astype("object")
    p = p.assign(
        APPROVED=approved.astype("int8"), REFUSED=refused.astype("int8"),
        CANCELED=(st == "Canceled").astype("int8"),
        APPLIED_30D=(p.DAYS_DECISION >= -30).astype("int8"),
        REFUSED_DAYS=p.DAYS_DECISION.where(refused),
        ASKED_VS_GRANTED=(p.AMT_APPLICATION / p.AMT_CREDIT.replace(0, np.nan)).where(approved),
        RUNNING=running.astype("int8"), RUNNING_ANNUITY=p.AMT_ANNUITY.where(running),
        REJECT_HC=(reason == "HC").astype("int8"), REJECT_LIMIT=(reason == "LIMIT").astype("int8"),
        REJECT_SCO=(reason == "SCO").astype("int8"),
        HIGH_YIELD=(p.NAME_YIELD_GROUP.astype("object") == "high").astype("int8"),
        CNT_PAYMENT_APPROVED=p.CNT_PAYMENT.where(approved),
    )
    g = p.groupby("SK_ID_CURR")
    out = g.agg(PREV_COUNT=("APPROVED", "size"), PREV_APPROVED_COUNT=("APPROVED", "sum"),
                PREV_REFUSED_COUNT=("REFUSED", "sum"), PREV_CANCELED_COUNT=("CANCELED", "sum"),
                PREV_REFUSED_SHARE=("REFUSED", "mean"), PREV_DAYS_DECISION_MAX=("DAYS_DECISION", "max"),
                PREV_LAST_REFUSAL_DAYS=("REFUSED_DAYS", "max"), PREV_APPLIED_30D_COUNT=("APPLIED_30D", "sum"),
                PREV_APPROVED_CREDIT_MEAN=("AMT_CREDIT", "mean"), PREV_ASKED_VS_GRANTED_MEAN=("ASKED_VS_GRANTED", "mean"),
                PREV_TERM_MEAN=("CNT_PAYMENT_APPROVED", "mean"), PREV_RUNNING_COUNT=("RUNNING", "sum"),
                PREV_RUNNING_ANNUITY_SUM=("RUNNING_ANNUITY", "sum"), PREV_REJECT_HC_COUNT=("REJECT_HC", "sum"),
                PREV_REJECT_LIMIT_COUNT=("REJECT_LIMIT", "sum"), PREV_REJECT_SCO_COUNT=("REJECT_SCO", "sum"),
                PREV_HIGH_YIELD_SHARE=("HIGH_YIELD", "mean"))
    return out


def build(interim: Path) -> pd.DataFrame:
    return features(load(interim, "previous_application", SOURCES["previous_application"]))
