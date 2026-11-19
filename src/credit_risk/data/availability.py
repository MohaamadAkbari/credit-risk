"""Build the feature-by-feature leakage table (Phase 2).

For every column of the seven training tables it records: what it is, whether it is known on the
application date, the evidence checked in the data, the handling rule, the fairness-proxy risk and
the ablation stage (A main table, B + bureau, C + Home Credit history) where it may enter.

Verdicts are written by hand below; the evidence columns (missing %, min, max, count of the
365243 marker, count of dates after the application) are computed from the data every run, so the
table cannot silently disagree with the data.

Outputs:
  configs/feature_availability.csv   machine-readable; tests and the feature pipeline read it
  reports/leakage_table.md           the same table for people

Usage: python -m credit_risk.data.availability   (or: make leakage)
Needs data/interim/ (make interim) and the raw column descriptions.
"""
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

STAGE = {"application_train": "A", "bureau": "B", "bureau_balance": "B",
         "previous_application": "C", "POS_CASH_balance": "C",
         "installments_payments": "C", "credit_card_balance": "C"}

VERDICTS = {
    "key": "Identifier: join key only, never a feature",
    "label": "Label: never an input",
    "protected": "Known at application, but excluded from inputs; used for fairness only (D23)",
    "ok": "Known at application",
    "ok_recode": "Known at application; contains a placeholder that must be recoded",
    "ok_planned": "Known at application; positive values are planned (contracted) future dates",
    "ok_filter": "Known at application except a few rows, which are dropped",
    "review": "Assumed known at application; timing or source not documented, flagged",
    "exclude": "Known at application, but excluded from inputs by policy: describes the process, not the applicant",
    "drop": "Not usable",
}

# Main-table columns that carry credit-bureau information enter at stage B, not A, so that the
# A -> B ablation (D25) measures everything the bureau adds (Phase 2 review, finding 2; D50).
STAGE_OVERRIDE = {("application_train", c): "B" for c in [
    "EXT_SOURCE_3", "AMT_REQ_CREDIT_BUREAU_HOUR", "AMT_REQ_CREDIT_BUREAU_DAY", "AMT_REQ_CREDIT_BUREAU_WEEK",
    "AMT_REQ_CREDIT_BUREAU_MON", "AMT_REQ_CREDIT_BUREAU_QRT", "AMT_REQ_CREDIT_BUREAU_YEAR"]}

# Hand-written verdicts. (table, column) -> (verdict, rule, proxy_risk)
# Columns not listed take the table default further down.
R = {}
def r(t, cols, verdict, rule="", proxy=""):
    for c in cols.split():
        R[(t, c)] = (verdict, rule, proxy)

A = "application_train"
r(A, "SK_ID_CURR", "key",
  "Unit of prediction. The split groups IDs by person (588 people have two IDs; D49). Not a hidden time order: default 7.9-8.3% and mean EXT_SOURCE_3 flat across ID deciles")
r(A, "TARGET", "label", "Payment difficulty on early instalments, not write-off (D18)")
r(A, "CODE_GENDER", "protected", "Exclude from inputs; 4 rows 'XNA' set to missing in the fairness audit")
r(A, "DAYS_BIRTH", "protected", "Exclude from inputs; derive age band for the fairness audit")
r(A, "DAYS_EMPLOYED", "ok_recode",
  "365243 (55,374 rows, all pensioners or unemployed) -> missing + flag EMPLOYED_NA", "high (age)")
r(A, "ORGANIZATION_TYPE", "ok_recode", "'XNA' is the same 55,374 rows as DAYS_EMPLOYED=365243; keep as its own level", "high (gender)")
r(A, "OCCUPATION_TYPE", "ok", "31% missing; missing is its own level (mostly pensioners)", "high (gender)")
r(A, "NAME_INCOME_TYPE", "ok", "Rare levels (<25 rows: Unemployed, Student, Businessman, Maternity leave) grouped", "medium (age)")
r(A, "FLAG_EMP_PHONE", "ok",
  "Equals 1 - EMPLOYED_NA in all but 12 rows: it is the pensioner / unemployed flag, not a phone signal. Dropped in features as a duplicate of EMPLOYED_NA", "high (age)")
r(A, "FLAG_OWN_CAR", "ok", "", "medium (gender)")
r(A, "FLAG_DOCUMENT_6", "ok", "", "medium (age)")
r(A, "AMT_INCOME_TOTAL", "ok", "One value of 117,000,000 and 250 rows above 1,000,000: cap at the training 99.9th percentile", "medium (gender)")
r(A, "CNT_CHILDREN CNT_FAM_MEMBERS", "ok", "Cap extreme counts (max 19 and 20)", "medium (age)")
r(A, "EXT_SOURCE_1", "review",
  "External score, provider and scoring date not documented; treat as bought at application. Strongest age proxy (r = 0.60 where present)", "high (age)")
r(A, "EXT_SOURCE_2", "review",
  "External score, provider and scoring date not documented; treat as bought at application. 202 values below 0.001 form a continuous tail (43.6% default): real low scores, kept")
r(A, "EXT_SOURCE_3", "review",
  "External score, provider and scoring date not documented. Missing for 96.9% of applicants with no bureau record vs 6.9% of the rest: bureau-derived, so stage B (D50)")
r(A, "OBS_30_CNT_SOCIAL_CIRCLE DEF_30_CNT_SOCIAL_CIRCLE DEF_60_CNT_SOCIAL_CIRCLE", "review",
  "Defaults among the applicant's social circle; how and when it is observed is not documented")
r(A, "OBS_60_CNT_SOCIAL_CIRCLE", "review",
  "Social-circle count, timing not documented. Correlates 0.998 with OBS_30_CNT_SOCIAL_CIRCLE: dropped in features as a duplicate")
r(A, "DAYS_REGISTRATION DAYS_ID_PUBLISH", "ok", "All values <= 0 (checked)", "medium (age)")
r(A, "DAYS_LAST_PHONE_CHANGE", "ok_recode",
  "All values <= 0. 0 in 37,672 rows against 2,812 at -1 (9.7% default): a process value, not a change date -> missing + flag PHONE_CHANGE_DAY0", "medium (age)")
r(A, "OWN_CAR_AGE", "ok_recode",
  "Missing = no car. 64 (2,443 rows) and 65 (891 rows) against 1-2 rows at 63 and 69: codes, not ages -> missing + flag CAR_AGE_CODED")
r(A, "AMT_REQ_CREDIT_BUREAU_HOUR AMT_REQ_CREDIT_BUREAU_DAY AMT_REQ_CREDIT_BUREAU_WEEK AMT_REQ_CREDIT_BUREAU_MON AMT_REQ_CREDIT_BUREAU_QRT AMT_REQ_CREDIT_BUREAU_YEAR",
  "ok", "Bureau enquiries before the application. Missing for 94.3% of applicants with no bureau record and 0% of the rest: bureau information, so stage B (D50). QRT has one value of 261, cap")
r(A, "FLAG_MOBIL FLAG_DOCUMENT_2 FLAG_DOCUMENT_4 FLAG_DOCUMENT_7 FLAG_DOCUMENT_10 FLAG_DOCUMENT_12 FLAG_DOCUMENT_17",
  "ok", "Near-constant (fewer than 100 rows differ); drop in Phase 3 for lack of signal, not for leakage")
r(A, "HOUR_APPR_PROCESS_START", "exclude",
  "Default 10-11% at 5-7 am vs 6.5% at 5 pm, but mostly region / time zone: 22% of region-3 applications start by 7 am vs 0.6% in region 1, and the gap shrinks within region. Not about the applicant; excluded (D51)")
r(A, "WEEKDAY_APPR_PROCESS_START", "exclude",
  "Process metadata with no signal (7.8-8.4% default by weekday); excluded with the hour (D51)")

B = "bureau"
r(B, "SK_ID_CURR SK_ID_BUREAU", "key", "Join bureau -> application on SK_ID_CURR; bureau_balance on SK_ID_BUREAU")
r(B, "DAYS_CREDIT", "ok", "All <= 0. 852 credits opened within 7 days before the application (629 training applicants, 19.7% default): legitimate signal, but check it is not the current loan reported back (amounts match in only 0.5%)")
r(B, "DAYS_CREDIT_ENDDATE", "ok_planned", "Positive in 602,603 rows = remaining contracted term; 134 rows below -40,000 days (about 110 years) are errors -> missing")
r(B, "DAYS_ENDDATE_FACT", "ok", "All <= 0; 1 row below -40,000 -> missing; 20 rows end before they start -> missing")
r(B, "DAYS_CREDIT_UPDATE", "ok_filter", "17 rows dated 10 to 372 days AFTER the application: drop those bureau rows (D32). 95 rows below -40,000 -> missing")
r(B, "CREDIT_DAY_OVERDUE AMT_CREDIT_MAX_OVERDUE AMT_CREDIT_SUM_OVERDUE", "ok", "Defined 'at the time of application' in the column description")
r(B, "AMT_CREDIT_SUM_DEBT AMT_CREDIT_SUM_LIMIT", "ok", "Negative values (8,418 debt, 351 limit) are overpayments or errors: keep sign, clip in features")
r(B, "CREDIT_CURRENCY", "ok", "99.9% currency 1; amounts in other currencies are not comparable, exclude those rows from amount sums")

BB = "bureau_balance"
r(BB, "SK_ID_BUREAU", "key", "11.4% of rows belong to bureau credits not in bureau.csv: unjoinable, ignored")
r(BB, "MONTHS_BALANCE", "ok", "Max 0. Month 0 (610,965 rows) is the application month; build features with month <= 0 and test month <= -1 as an ablation")
r(BB, "STATUS", "ok", "C closed, X unknown, 0 no delay, 1-5 days-past-due buckets")

P = "previous_application"
r(P, "SK_ID_PREV SK_ID_CURR", "key", "One applicant has 0 to 77 earlier applications")
r(P, "DAYS_DECISION", "ok", "All <= -1: every earlier application was decided before the current one")
r(P, "DAYS_FIRST_DRAWING DAYS_FIRST_DUE DAYS_LAST_DUE DAYS_TERMINATION", "ok_recode",
  "365243 = no date (not yet happened or never); real values all <= -2. Recode to missing + flag")
r(P, "DAYS_LAST_DUE_1ST_VERSION", "ok_planned", "224,392 positive values = originally planned last due date; 365243 -> missing")
r(P, "NAME_CONTRACT_STATUS CODE_REJECT_REASON", "ok",
  "Outcome of an earlier, already decided application. Share refused is a strong signal (>50% refused: 15.9% default). Checked that no earlier row is the current loan: 648 applicants have one with the same amount and annuity (465 refused: re-applications); 1,415 had an approval in the last 7 days, default 8.3% = portfolio, so no leak")
r(P, "RATE_INTEREST_PRIMARY RATE_INTEREST_PRIVILEGED", "ok", "99.6% missing: drop for lack of data")
r(P, "AMT_CREDIT", "ok", "0 for refused, cancelled and unused applications (336,768 rows): use only for approved ones")
r(P, "SELLERPLACE_AREA", "ok", "-1 (762,675 rows) is a no-value marker -> missing")
r(P, "AMT_DOWN_PAYMENT RATE_DOWN_PAYMENT", "ok", "A few tiny negative values -> 0")

POS = "POS_CASH_balance"
r(POS, "SK_ID_PREV SK_ID_CURR", "key", "3.4% of SK_ID_PREV not in previous_application; kept (dates are still before the application)")
r(POS, "MONTHS_BALANCE", "ok", "Max -1: all snapshots before the application month")

INST = "installments_payments"
r(INST, "SK_ID_PREV SK_ID_CURR", "key", "9.2% of SK_ID_PREV not in previous_application; kept")
r(INST, "DAYS_INSTALMENT", "ok", "All <= -1")
r(INST, "DAYS_ENTRY_PAYMENT", "ok", "All <= -1; 392 payments more than a year before the due date look like errors -> cap earliness")
r(INST, "AMT_PAYMENT", "ok", "2,905 missing (unpaid); 653,483 rows share (loan, version, number): split payments, sum before computing lateness")
r(INST, "NUM_INSTALMENT_VERSION", "ok", "0 = credit card (4.1 million rows)")

CC = "credit_card_balance"
r(CC, "SK_ID_PREV SK_ID_CURR", "key", "28.2% of SK_ID_PREV not in previous_application; kept. Only 28.3% of applicants have card data")
r(CC, "MONTHS_BALANCE", "ok", "Max -1: all snapshots before the application month")
r(CC, "AMT_BALANCE AMT_RECEIVABLE_PRINCIPAL AMT_RECIVABLE AMT_TOTAL_RECEIVABLE", "ok", "Negative values = credit balance; keep. The three receivable columns are near-duplicates of the balance")

DEFAULT_RULE = {
    A: ("ok", "Application form or Home Credit's own data on the application day"),
    B: ("ok", "Other lenders' credits as reported on the application date"),
    BB: ("ok", ""),
    P: ("ok", "Describes an earlier application decided before the current one"),
    POS: ("ok", "Monthly snapshot of an earlier loan, before the application month"),
    INST: ("ok", "Instalment of an earlier loan, due and paid before the application"),
    CC: ("ok", "Monthly snapshot of an earlier card, before the application month"),
}
HOUSING = ("_AVG", "_MODE", "_MEDI")
DAY_COLS_PREFIX = ("DAYS_", "MONTHS_")


def describe(desc: pd.DataFrame, table: str, col: str) -> str:
    key = "application_{train|test}.csv" if table == A else f"{table}.csv"
    alt = {"SK_ID_BUREAU": "SK_BUREAU_ID"}.get(col, col)
    m = desc[(desc.Table == key) & (desc.Row.isin([col, alt]))]
    return "" if m.empty else str(m.Description.iloc[0]).strip()


def build(interim: Path, raw: Path, out_csv: Path, out_md: Path) -> pd.DataFrame:
    desc = pd.read_csv(raw / "HomeCredit_columns_description.csv", encoding="latin-1")
    rows = []
    for t in STAGE:
        cols = pq.ParquetFile(interim / f"{t}.parquet").schema_arrow.names
        for c in cols:
            s = pd.read_parquet(interim / f"{t}.parquet", columns=[c])[c]
            num = pd.api.types.is_numeric_dtype(s)
            verdict, rule, proxy = R.get((t, c), (None, "", ""))
            if verdict is None:
                verdict, rule = DEFAULT_RULE[t]
                if t == A and c.endswith(HOUSING):
                    rule = "Building statistics; 48-70% missing, mostly as one block (47% of rows lack all 47). Missing is informative (9.3% vs 7.0% default)"
            if not rule:
                rule = DEFAULT_RULE[t][1]
            is_day = c.startswith(DAY_COLS_PREFIX) and num
            real = s[s != 365243] if is_day else s
            stage = STAGE_OVERRIDE.get((t, c), STAGE[t]) if verdict not in ("key", "label", "protected", "exclude") else "-"
            rows.append(dict(
                table=t, column=c, stage=stage,
                verdict=verdict, known_at_application=VERDICTS[verdict],
                missing_pct=round(100 * s.isna().mean(), 1),
                min=round(float(real.min()), 4) if num and real.notna().any() else "",
                max=round(float(real.max()), 4) if num and real.notna().any() else "",
                n_365243=int((s == 365243).sum()) if is_day else "",
                n_after_application=int((real > 0).sum()) if is_day else "",
                proxy_risk=proxy, rule=rule, description=describe(desc, t, c)))
        print(t, "done")
    out = pd.DataFrame(rows)
    out.to_csv(out_csv, index=False)
    write_markdown(out, out_md)
    return out


def write_markdown(df: pd.DataFrame, path: Path) -> None:
    counts = df.groupby(["table", "verdict"]).size().unstack(fill_value=0)
    lines = [
        "# Feature-by-feature leakage table (Phase 2)", "",
        "*Generated by `make leakage` (`credit_risk.data.availability`) from the data; do not edit by hand. "
        "Machine-readable copy: `configs/feature_availability.csv`.*", "",
        "**The one question for every column: was this value known on the application date?** "
        "The data stores every date as days (or months) relative to the application, so a value above zero "
        "would be after the decision. `n_after_application` counts those (365243, a no-date marker, excluded). "
        "Only two kinds of positive dates exist: planned end dates, which are known in advance, and 17 bureau "
        "update dates, whose rows are dropped.", "",
        "## Verdicts", "",
        "| Verdict | Meaning |", "| --- | --- |",
        *[f"| `{k}` | {v} |" for k, v in VERDICTS.items() if k in set(df.verdict)], "",
        "**Stage** is the ablation in which a column may first enter the model (D25): A application form, "
        "B + credit-bureau information (the bureau tables and the seven bureau-derived main-table columns, D50), "
        "C + Home Credit history. **Proxy risk** marks columns that predict gender or age "
        "well (see `reports/eda_summary.md`, section 7).", "",
        "## Count by table", "",
        "| Table | " + " | ".join(f"`{c}`" for c in counts.columns) + " |",
        "| --- | " + " | ".join("---" for _ in counts.columns) + " |",
        *[f"| {t} | " + " | ".join(str(v) for v in row) + " |" for t, row in counts.iterrows()], "",
        "## Findings that change the pipeline", "",
        "1. **No column is a hidden copy of the outcome.** Every past-event date is on or before the application.",
        "2. **17 bureau rows** were updated 10 to 372 days after the application. Drop them.",
        "3. **Planned dates are positive and legitimate:** `DAYS_CREDIT_ENDDATE` (602,603 rows) and "
        "`DAYS_LAST_DUE_1ST_VERSION` (224,392 rows).",
        "4. **365243 means \"no date\"** in `DAYS_EMPLOYED` and five `previous_application` columns. Recode to missing plus a flag.",
        "5. **`bureau_balance` month 0** is the application month itself. Use it, but test month <= -1 as an ablation.",
        "6. **Seven columns have undocumented timing** (`review`): the three external scores and the four social-circle "
        "counts. They are kept on the assumption that the lender buys them at application; a real deployment must confirm this with the provider.",
        "7. **Gender and age are excluded, but other columns stand in for them** (proxy risk). Excluding them does not make the model blind; the fairness audit must measure outcomes.",
        "8. **Seven main-table columns are bureau information** (`EXT_SOURCE_3`, six `AMT_REQ_CREDIT_BUREAU_*`): they are almost always missing "
        "when the applicant has no bureau record. They move to stage B (D50).",
        "9. **Three more placeholders:** `OWN_CAR_AGE` 64/65, `DAYS_LAST_PHONE_CHANGE` 0 (recoded with flags); `EXT_SOURCE_2` near 0 checked and kept.",
        "10. **Application hour and weekday are excluded** (`exclude`, D51): they describe the process and mostly reflect region.",
        "11. **No earlier application is the current loan in disguise**, and the ID is not a hidden time order (checked).",
        "",
    ]
    for t in STAGE:
        sub = df[df.table == t]
        lines += [f"## {t} ({len(sub)} columns)", "",
                  "| Column | Stage | Verdict | Missing % | Min | Max | 365243 | After appl. | Proxy risk | Rule / evidence |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for _, x in sub.iterrows():
            def f(v):
                if v == "" or pd.isna(v):
                    return ""
                return f"{v:,.0f}" if isinstance(v, (int, float)) and abs(v) >= 1000 else f"{v:g}" if isinstance(v, float) else str(v)
            rule = (x.rule or "").replace("|", "/")
            lines.append(f"| `{x.column}` | {x.stage} | `{x.verdict}` | {x.missing_pct:g} | {f(x['min'])} | {f(x['max'])} | "
                         f"{f(x.n_365243)} | {f(x.n_after_application)} | {x.proxy_risk} | {rule} |")
        lines.append("")
    path.write_text("\n".join(lines))
    print("wrote", path)


def main(argv: list[str] | None = None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Build the feature-by-feature leakage table.")
    ap.add_argument("--interim", default="data/interim", type=Path)
    ap.add_argument("--raw", default="data/home-credit-default-risk", type=Path)
    ap.add_argument("--out-csv", default="configs/feature_availability.csv", type=Path)
    ap.add_argument("--out-md", default="reports/leakage_table.md", type=Path)
    a = ap.parse_args(argv)
    build(a.interim, a.raw, a.out_csv, a.out_md)


if __name__ == "__main__":
    main()
