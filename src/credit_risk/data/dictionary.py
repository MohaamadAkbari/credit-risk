"""Data dictionary for every column of the seven training tables (Phase 2).

The EDA documented each column's leakage verdict, but not what the column *is*: its family, kind,
unit, typical range, levels, and how to chart it. This module writes that, from the data:

  group       the business family the column belongs to (e.g. "Loan requested", "External scores")
  kind        key, label, flag, amount, count, days, months, score (normalised 0-1), rating, category, number
  unit        what one unit means (currency unit, days before the application, ...)
  range       1st-99th percentile with the median, in readable units (days shown as years); markers excluded
  levels      number of levels and the three most common, for text columns
  special     Kaggle's own note on the column (normalised, hashed, rounded, recoded, time relative)
  iv, shape   for main-table columns: information value and risk shape on the TRAINING fold only
  chart       how this kind of column is best visualised, used by the stakeholder dashboard

Outputs: configs/data_dictionary.csv, reports/data_dictionary.md
Usage: python -m credit_risk.data.dictionary   (or: make dictionary)
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from credit_risk.data.availability import STAGE
from credit_risk.features.shapes import analyse
from credit_risk.paths import AVAILABILITY, INTERIM, NO_DATE, PROCESSED, RAW

TABLE_GROUP = {"bureau": "Credits at other lenders", "bureau_balance": "Monthly status of bureau credits",
               "previous_application": "Earlier Home Credit applications", "POS_CASH_balance": "Monthly status of earlier POS / cash loans",
               "installments_payments": "Instalments of earlier loans", "credit_card_balance": "Monthly status of earlier credit cards"}
MAIN_GROUPS = [  # (regex on the column name, group) for application_train, first match wins
    (r"^SK_ID_", "Identifiers"), (r"^TARGET$", "Outcome (label)"),
    (r"^(CODE_GENDER|DAYS_BIRTH|CNT_CHILDREN|CNT_FAM_MEMBERS|NAME_FAMILY_STATUS)$", "Demographics and family"),
    (r"^(AMT_INCOME_TOTAL|NAME_INCOME_TYPE|DAYS_EMPLOYED|OCCUPATION_TYPE|ORGANIZATION_TYPE|NAME_EDUCATION_TYPE)$", "Income, work and education"),
    (r"^(NAME_CONTRACT_TYPE|AMT_CREDIT|AMT_ANNUITY|AMT_GOODS_PRICE|NAME_TYPE_SUITE)$", "Loan requested"),
    (r"^(FLAG_OWN_CAR|OWN_CAR_AGE|FLAG_OWN_REALTY|NAME_HOUSING_TYPE)$", "Assets and housing"),
    (r"(_AVG|_MODE|_MEDI)$", "Building statistics"),
    (r"^(REGION_|REG_|LIVE_)", "Region and address"),
    (r"^(FLAG_MOBIL|FLAG_EMP_PHONE|FLAG_WORK_PHONE|FLAG_CONT_MOBILE|FLAG_PHONE|FLAG_EMAIL|DAYS_LAST_PHONE_CHANGE)$", "Contact details"),
    (r"^(DAYS_REGISTRATION|DAYS_ID_PUBLISH|FLAG_DOCUMENT_)", "Documents and registration"),
    (r"^EXT_SOURCE_", "External scores"), (r"_CNT_SOCIAL_CIRCLE$", "Social circle"),
    (r"^AMT_REQ_CREDIT_BUREAU_", "Credit-bureau enquiries"), (r"_APPR_PROCESS_START$", "Application process"),
]
UNIT = {"key": "identifier", "label": "1 = payment difficulty", "flag": "yes / no", "amount": "currency units (not stated)",
        "count": "count", "days": "days before the application", "months": "months before the application",
        "score": "normalised, 0-1", "rating": "ordinal level", "category": "text levels", "number": "as recorded"}
CHART = {"key": "Join coverage: share of applicants with rows",
         "label": "Headline rate, then default rate by segment",
         "flag": "Two bars: share of applicants and default rate for each value",
         "amount": "Histogram on a log scale, with default rate per bin",
         "count": "Bar per value (large values capped), with default rate per value",
         "days": "Histogram in years, with default rate per bin",
         "months": "Histogram of history length",
         "score": "Histogram, with default rate per decile",
         "rating": "Bar per level, with default rate",
         "category": "Bars per level sorted by default rate, with counts; rare levels grouped",
         "number": "Histogram, with default rate per bin"}
# Codes that are not values (leakage table, D55): left out of the range and counted in n_marker
MARKERS = {"SELLERPLACE_AREA": [-1], "OWN_CAR_AGE": [64, 65], "DAYS_LAST_PHONE_CHANGE": [0]}
UNIT_BY_COLUMN = {"HOUR_APPR_PROCESS_START": "hour of day, rounded", "OWN_CAR_AGE": "years",
                  "SELLERPLACE_AREA": "seller area code", "CNT_PAYMENT": "instalments",
                  "CREDIT_DAY_OVERDUE": "days overdue", "SK_DPD": "days past due", "SK_DPD_DEF": "days past due",
                  "DAYS_CREDIT_ENDDATE": "days relative to the application (negative years = planned, in the future)",
                  "DAYS_LAST_DUE_1ST_VERSION": "days relative to the application (negative years = planned, in the future)"}


def group_of(table: str, col: str) -> str:
    if table != "application_train":
        return "Identifiers" if col.startswith("SK_ID_") else TABLE_GROUP[table]
    return next(g for rx, g in MAIN_GROUPS if re.search(rx, col))


def kind_of(col: str, s: pd.Series, verdict: str, special: str) -> str:
    if verdict == "key":
        return "key"
    if verdict == "label":
        return "label"
    if not pd.api.types.is_numeric_dtype(s):
        vals = set(s.dropna().unique())
        return "flag" if vals <= {"Y", "N"} else "category"
    if col.startswith("DAYS_"):
        return "days"
    if col.startswith("MONTHS_"):
        return "months"
    if set(np.unique(s.dropna())) <= {0, 1}:
        return "flag"
    if "normalized" in special:
        return "score"
    if col.startswith("REGION_RATING"):
        return "rating"
    if col.startswith("HOUR_"):
        return "number"
    if col.startswith(("AMT_REQ_", "CNT_", "OBS_", "DEF_", "SK_DPD", "NUM_INSTALMENT")):
        return "count"
    if col.startswith("AMT_"):
        return "amount"
    return "number"


def fmt(v: float) -> str:
    if pd.isna(v):
        return ""
    a = abs(v)
    return f"{v:,.0f}" if a >= 100 else f"{v:.1f}" if a >= 10 else f"{v:.3g}"


def describe_range(kind: str, s: pd.Series) -> tuple[str, dict]:
    names = ["min", "p01", "p50", "p99", "max"]
    if not pd.api.types.is_numeric_dtype(s) or s.notna().sum() == 0:
        return "", dict.fromkeys(names, np.nan)
    q = s.astype("float64").quantile([0, .01, .5, .99, 1]).to_numpy()
    stats = dict(zip(names, [float(x) for x in q], strict=True))
    if kind in ("key", "category", "flag", "label"):
        return "", stats
    if kind == "days":
        yrs = -s / 365.25
        lo, md, hi = yrs.quantile([.01, .5, .99])
        return f"{fmt(lo)}-{fmt(hi)} years (median {fmt(md)})", stats
    if kind == "months":
        mo = -s
        lo, md, hi = mo.quantile([.01, .5, .99])
        return f"{fmt(lo)}-{fmt(hi)} months (median {fmt(md)})", stats
    p01, p50, p99 = stats["p01"], stats["p50"], stats["p99"]
    return f"{fmt(p01)}-{fmt(p99)} (median {fmt(p50)})", stats


def levels_of(s: pd.Series) -> tuple[int, str]:
    vc = s.value_counts(normalize=True, dropna=True)
    return int(len(vc)), "; ".join(f"{k} {100 * v:.1f}%" for k, v in vc.head(3).items())


def build(interim: Path, raw: Path, availability: Path, processed: Path) -> pd.DataFrame:
    avail = pd.read_csv(availability).set_index(["table", "column"])
    desc = pd.read_csv(raw / "HomeCredit_columns_description.csv", encoding="latin-1")
    desc["Special"] = desc.Special.fillna("").str.strip()
    special = {}
    for r in desc.itertuples():
        t = "application_train" if r.Table.startswith("application") else r.Table.replace(".csv", "")
        special[(t, {"SK_BUREAU_ID": "SK_ID_BUREAU"}.get(r.Row.strip(), r.Row.strip()))] = r.Special
    split = pd.read_parquet(processed / "split.parquet").set_index("SK_ID_CURR")
    train_ids = split.index[split.fold == "train"]
    rows = []
    for t in STAGE:
        cols = pq.ParquetFile(interim / f"{t}.parquet").schema_arrow.names
        y = None
        if t == "application_train":
            y = pd.read_parquet(interim / f"{t}.parquet", columns=["SK_ID_CURR", "TARGET"]).set_index("SK_ID_CURR").TARGET
        for c in cols:
            s = pd.read_parquet(interim / f"{t}.parquet", columns=[c])[c]
            a = avail.loc[(t, c)]
            sp = special.get((t, c), "")
            kind = kind_of(c, s, a.verdict, sp)
            n_marker = 0
            if kind == "days":
                n_marker = int((s == NO_DATE).sum())
                s = s.mask(s == NO_DATE)
            if c in MARKERS:
                is_code = s.isin(MARKERS[c])
                n_marker += int(is_code.sum())
                s = s.mask(is_code)
            rng, stats = describe_range(kind, s)
            n_levels, top = levels_of(s) if kind in ("category", "flag") else (int(s.nunique()), "")
            iv = shape = ""
            if y is not None and kind not in ("key", "label"):
                x = pd.Series(s.to_numpy(), index=y.index).loc[train_ids]
                r = analyse(x, y.loc[train_ids].astype(int))
                iv, shape = round(r["iv"], 4), r["shape"]
            rows.append(dict(
                table=t, column=c, group=group_of(t, c), kind=kind, unit=UNIT_BY_COLUMN.get(c, UNIT[kind]), description=a.description,
                special=sp, verdict=a.verdict, stage=a.stage, missing_pct=a.missing_pct, n_unique=n_levels,
                top_levels=top, range=rng, n_marker=n_marker, iv_train=iv, shape_train=shape, chart=CHART[kind],
                **{k: round(v, 4) if pd.notna(v) else np.nan for k, v in stats.items()}))
            del s
        print(t, "done")
    return pd.DataFrame(rows)


def write_markdown(df: pd.DataFrame, path: Path) -> None:
    lines = ["# Data dictionary (Phase 2)", "",
             "*Generated by `make dictionary` (`credit_risk.data.dictionary`); do not edit by hand. Machine-readable copy: "
             "`configs/data_dictionary.csv`. Leakage verdicts: `reports/leakage_table.md`.*", "",
             "**How to read it.** Each column has a *group* (the business family it belongs to), a *kind* (what sort of "
             "value it holds, which decides how it is charted) and a *range*: the 1st to 99th percentile with the median, "
             "markers such as 365243 removed, and day counts shown as years before the application. *IV* is the information "
             "value against default on the training fold (main table only; the related tables enter the model through "
             "aggregated features, see `reports/feature_shapes.md`). *Special* is Kaggle's own note on the column.", "",
             "## Kinds and how each is charted", "", "| Kind | Unit | Columns | Chart |", "| --- | --- | --- | --- |"]
    for k, g in df.groupby("kind"):
        lines.append(f"| {k} | {UNIT[k]} | {len(g)} | {CHART[k]} |")
    lines += ["", "## Groups", "", "| Table | Group | Columns | Kinds |", "| --- | --- | --- | --- |"]
    for (t, gname), g in df.groupby(["table", "group"], sort=False):
        lines.append(f"| {t} | {gname} | {len(g)} | {', '.join(f'{k} {v}' for k, v in g.kind.value_counts().items())} |")
    for t, g in df.groupby("table", sort=False):
        lines += ["", f"## {t} ({len(g)} columns)", "",
                  "| Column | Group | Kind | Description | Range (p1-p99, median) / top levels | Missing % | IV | Special |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in g.itertuples():
            d = (r.description if isinstance(r.description, str) else "").replace("|", "/")
            val = r.range or (f"{r.n_unique} levels: {r.top_levels}" if r.top_levels else "")
            iv = "" if r.iv_train == "" or pd.isna(r.iv_train) else f"{float(r.iv_train):.3f}"
            lines.append(f"| `{r.column}` | {r.group} | {r.kind} | {d} | {val.replace('|', '/')} | {r.missing_pct:g} | {iv} | {r.special} |")
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build the data dictionary.")
    ap.add_argument("--interim", default=INTERIM, type=Path)
    ap.add_argument("--raw", default=RAW, type=Path)
    ap.add_argument("--availability", default=AVAILABILITY, type=Path)
    ap.add_argument("--processed", default=PROCESSED, type=Path)
    ap.add_argument("--out-csv", default=Path("configs/data_dictionary.csv"), type=Path)
    ap.add_argument("--out-md", default=Path("reports/data_dictionary.md"), type=Path)
    a = ap.parse_args(argv)
    df = build(a.interim, a.raw, a.availability, a.processed)
    df.to_csv(a.out_csv, index=False)
    write_markdown(df, a.out_md)
    print(df.kind.value_counts().to_dict())
    print(df.group.value_counts().to_dict())


if __name__ == "__main__":
    main()
