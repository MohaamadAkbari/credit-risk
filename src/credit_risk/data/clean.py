"""Deterministic cleaning rules, one function per table (decisions D32, D37).

Each rule comes from reports/leakage_table.md. Nothing here is fitted to data: anything that
learns from values (caps, rare levels, imputation) lives in credit_risk.features.preprocess and
is fitted on the training fold only (D21).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from credit_risk.paths import NO_DATE

ERROR_DATE = -40_000  # about 110 years before the application: data errors


def _na_where(s: pd.Series, mask) -> pd.Series:
    return s.mask(mask)


def clean_application(df: pd.DataFrame) -> pd.DataFrame:
    """Recode the employment no-date marker (pensioners) and the 4 'XNA' genders."""
    df = df.copy()
    if "DAYS_EMPLOYED" in df:
        na = df["DAYS_EMPLOYED"] == NO_DATE
        df["EMPLOYED_NA"] = na.astype("int8")
        df["DAYS_EMPLOYED"] = _na_where(df["DAYS_EMPLOYED"], na)
    if "CODE_GENDER" in df:
        df["CODE_GENDER"] = df["CODE_GENDER"].astype("object").where(df["CODE_GENDER"] != "XNA")
    return df


def clean_bureau(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows updated after the application; null out impossible dates."""
    df = df[~(df["DAYS_CREDIT_UPDATE"] > 0)].copy()                  # 17 rows (D32)
    for c in ["DAYS_CREDIT_ENDDATE", "DAYS_ENDDATE_FACT", "DAYS_CREDIT_UPDATE"]:
        if c in df:
            df[c] = _na_where(df[c], df[c] < ERROR_DATE)
    if {"DAYS_ENDDATE_FACT", "DAYS_CREDIT"} <= set(df.columns):
        df["DAYS_ENDDATE_FACT"] = _na_where(df["DAYS_ENDDATE_FACT"], df["DAYS_ENDDATE_FACT"] < df["DAYS_CREDIT"])
    return df


def clean_bureau_balance(df: pd.DataFrame, max_month: int = 0) -> pd.DataFrame:
    """Keep months up to max_month (0 = application month, -1 for the stricter ablation)."""
    return df[df["MONTHS_BALANCE"] <= max_month]


PREV_DATES = ["DAYS_FIRST_DRAWING", "DAYS_FIRST_DUE", "DAYS_LAST_DUE_1ST_VERSION", "DAYS_LAST_DUE", "DAYS_TERMINATION"]


def clean_previous(df: pd.DataFrame) -> pd.DataFrame:
    """Recode 365243 and -1 markers; amounts of non-approved applications are not loans."""
    df = df.copy()
    for c in PREV_DATES:
        if c in df:
            df[c] = _na_where(df[c], df[c] == NO_DATE)
    if "SELLERPLACE_AREA" in df:
        df["SELLERPLACE_AREA"] = _na_where(df["SELLERPLACE_AREA"], df["SELLERPLACE_AREA"] == -1)
    if {"AMT_CREDIT", "NAME_CONTRACT_STATUS"} <= set(df.columns):
        df["AMT_CREDIT"] = _na_where(df["AMT_CREDIT"], df["NAME_CONTRACT_STATUS"] != "Approved")
    for c in ["AMT_DOWN_PAYMENT", "RATE_DOWN_PAYMENT"]:
        if c in df:
            df[c] = df[c].clip(lower=0)
    return df


INSTALMENT_KEY = ["SK_ID_CURR", "SK_ID_PREV", "NUM_INSTALMENT_VERSION", "NUM_INSTALMENT_NUMBER"]
MAX_EARLY_DAYS = 365


def clean_installments(df: pd.DataFrame) -> pd.DataFrame:
    """One row per instalment: split payments summed, lateness from the last payment.

    DAYS_LATE > 0 means paid late; earliness is capped at one year (392 rows were paid
    more than a year early, which looks like an error).
    """
    g = df.groupby(INSTALMENT_KEY, sort=False, observed=True)
    out = g.agg(DAYS_INSTALMENT=("DAYS_INSTALMENT", "max"),
                AMT_INSTALMENT=("AMT_INSTALMENT", "max"),
                DAYS_ENTRY_PAYMENT=("DAYS_ENTRY_PAYMENT", "max"),
                AMT_PAYMENT=("AMT_PAYMENT", "sum")).reset_index()
    paid_any = g["AMT_PAYMENT"].count().to_numpy() > 0
    out.loc[~paid_any, "AMT_PAYMENT"] = np.nan                      # never paid: missing, not 0
    out["DAYS_LATE"] = (out["DAYS_ENTRY_PAYMENT"] - out["DAYS_INSTALMENT"]).clip(lower=-MAX_EARLY_DAYS)
    return out
