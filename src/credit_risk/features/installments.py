"""Stage C: instalments of earlier Home Credit loans (due vs paid)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from credit_risk.data.clean import clean_installments
from credit_risk.data.io import load

SOURCES = {"installments_payments": [
    "SK_ID_CURR", "SK_ID_PREV", "NUM_INSTALMENT_VERSION", "NUM_INSTALMENT_NUMBER", "DAYS_INSTALMENT",
    "DAYS_ENTRY_PAYMENT", "AMT_INSTALMENT", "AMT_PAYMENT"]}


def features(inst: pd.DataFrame) -> pd.DataFrame:
    i = clean_installments(inst)
    late = i.DAYS_LATE > 0
    recent = i.DAYS_INSTALMENT >= -365
    i = i.assign(
        LATE=late.astype("float32").where(i.DAYS_LATE.notna()),
        LATE_DAYS=i.DAYS_LATE.clip(lower=0),
        LATE_1Y=late.astype("float32").where(i.DAYS_LATE.notna() & recent),
        UNPAID=i.AMT_PAYMENT.isna().astype("int8"),
        UNDERPAID=((i.AMT_PAYMENT < i.AMT_INSTALMENT - 1) | i.AMT_PAYMENT.isna()).astype("int8"),
        PAID_RATIO=i.AMT_PAYMENT / i.AMT_INSTALMENT.where(i.AMT_INSTALMENT > 0),
    )
    return i.groupby("SK_ID_CURR").agg(
        INST_COUNT=("LATE", "size"), INST_LATE_SHARE=("LATE", "mean"), INST_LATE_SHARE_1Y=("LATE_1Y", "mean"),
        INST_LATE_DAYS_MEAN=("LATE_DAYS", "mean"), INST_LATE_DAYS_MAX=("LATE_DAYS", "max"),
        INST_UNPAID_COUNT=("UNPAID", "sum"), INST_UNDERPAID_SHARE=("UNDERPAID", "mean"),
        INST_PAID_RATIO_MEAN=("PAID_RATIO", "mean"))


def build(interim: Path) -> pd.DataFrame:
    return features(load(interim, "installments_payments", SOURCES["installments_payments"]))
