"""Datasets for the stakeholder dashboard of the Phase 2 data understanding.

Writes one JSON file per dataset to reports/dashboard/, each {rows, meta}: rows are aggregates
(no applicant-level data), meta carries this script's own text and its inputs, so every number on
the dashboard can be traced and regenerated. Like the EDA, it describes all 307,511 labelled
applications; the information values come from the training fold only (configs/feature_shapes.csv).

Usage: python3 scripts/dashboard_data.py   (or: make dashboard-data)
Needs: data/interim (make interim), configs/data_dictionary.csv (make dictionary),
       configs/feature_shapes.csv (make shapes), executed notebooks/01_eda.ipynb.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

INTERIM = Path("data/interim")
OUT = Path("reports/dashboard")
CODE = Path(__file__).read_text()
NO_DATE = 365243


def rd(table, cols=None):
    return pd.read_parquet(INTERIM / f"{table}.parquet", columns=cols)


def clean(v):
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else round(float(v), 6)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def write(name, rows, inputs):
    rows = [{k: clean(v) for k, v in r.items()} for r in rows]
    meta = [{"label": "dashboard_data.py", "value": CODE, "type": "code", "lang": "python"},
            {"label": "Input", "value": inputs}]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps({"rows": rows, "meta": meta}, ensure_ascii=False))
    print(f"{name}: {len(rows)} rows")


app = rd("application_train")
te = rd("application_test")
y = app.TARGET.astype(int)
bur = rd("bureau", ["SK_ID_CURR", "DAYS_CREDIT_UPDATE", "DAYS_CREDIT_ENDDATE", "DAYS_ENDDATE_FACT", "DAYS_CREDIT"])
app["THIN_FILE"] = ~app.SK_ID_CURR.isin(bur.SK_ID_CURR)
app["AGE"] = -app.DAYS_BIRTH / 365.25
app["AGE_BAND"] = pd.cut(app.AGE, [18, 25, 35, 45, 55, 65, 100], right=False,
                         labels=["<25", "25-34", "35-44", "45-54", "55-64", "65+"]).astype(str)
app["CREDIT_TERM"] = app.AMT_CREDIT / app.AMT_ANNUITY
app["CREDIT_GOODS"] = app.AMT_CREDIT / app.AMT_GOODS_PRICE
app["ANNUITY_INCOME"] = app.AMT_ANNUITY / app.AMT_INCOME_TOTAL
emp = app.DAYS_EMPLOYED.where(app.DAYS_EMPLOYED != NO_DATE)
app["YEARS_EMPLOYED"] = -emp / 365.25

# ---- overview
tables = ["application_train", "application_test", "bureau", "bureau_balance", "previous_application",
          "POS_CASH_balance", "installments_payments", "credit_card_balance"]
ONE_ROW = {"application_train": "an application, with its outcome", "application_test": "an application, no outcome (Kaggle's test)",
           "bureau": "a credit at another lender", "bureau_balance": "a month of a bureau credit",
           "previous_application": "an earlier Home Credit application", "POS_CASH_balance": "a month of an earlier POS or cash loan",
           "installments_payments": "an instalment of an earlier loan", "credit_card_balance": "a month of an earlier credit card"}
import pyarrow.parquet as pq  # noqa: E402

trows = []
for t in tables:
    f = pq.ParquetFile(INTERIM / f"{t}.parquet")
    cov = None
    if "SK_ID_CURR" in f.schema_arrow.names and t not in ("application_train", "application_test"):
        ids = rd(t, ["SK_ID_CURR"]).SK_ID_CURR
        cov = 100 * app.SK_ID_CURR.isin(ids).mean()
    trows.append({"table": t, "rows": f.metadata.num_rows, "columns": len(f.schema_arrow.names),
                  "one_row_is": ONE_ROW[t], "train_applicants_with_rows_pct": cov})
write("tables", trows, "data/interim/*.parquet (all eight tables)")

dic = pd.read_csv("configs/data_dictionary.csv")
total_rows = sum(r["rows"] for r in trows)
kpis = [
    ("applications", "Labelled applications", len(app), "count"),
    ("defaults", "Applicants with payment difficulty", int(y.sum()), "count"),
    ("default_rate", "Default rate (payment difficulty)", y.mean(), "share"),
    ("default_rate_amount", "Default rate weighted by loan amount", (y * app.AMT_CREDIT).sum() / app.AMT_CREDIT.sum(), "share"),
    ("thin_file_share", "Applicants with no bureau record (thin file)", app.THIN_FILE.mean(), "share"),
    ("tables", "Tables", len(tables), "count"),
    ("rows_all_tables", "Rows across the eight tables", total_rows, "count"),
    ("columns_training", "Columns in the seven training tables", len(dic), "count"),
    ("kaggle_test_applications", "Kaggle test applications (no outcome)", len(te), "count"),
]
write("overview", [{"metric": k, "label": lbl, "value": v, "format": f} for k, lbl, v, f in kpis],
      "data/interim/application_train, application_test, bureau; configs/data_dictionary.csv")

# ---- dictionary (as generated)
keep = ["table", "column", "group", "kind", "unit", "description", "range", "top_levels", "n_unique", "missing_pct",
        "n_marker", "iv_train", "shape_train", "verdict", "stage", "special", "chart", "p01", "p50", "p99"]
d2 = dic[keep].copy()
d2["description"] = d2.description.fillna("")
write("dictionary", d2.replace({np.nan: None}).to_dict("records"), "configs/data_dictionary.csv (make dictionary)")

# ---- segments
SEG = {"Age band": "AGE_BAND", "Gender": "CODE_GENDER", "Thin file (no bureau record)": "THIN_FILE",
       "Contract type": "NAME_CONTRACT_TYPE", "Education": "NAME_EDUCATION_TYPE", "Income type": "NAME_INCOME_TYPE",
       "Family status": "NAME_FAMILY_STATUS", "Housing": "NAME_HOUSING_TYPE", "Occupation": "OCCUPATION_TYPE",
       "Region rating": "REGION_RATING_CLIENT_W_CITY", "Owns a car": "FLAG_OWN_CAR", "Owns property": "FLAG_OWN_REALTY"}
ORDER = {"AGE_BAND": ["<25", "25-34", "35-44", "45-54", "55-64", "65+"]}
srows = []
for seg, col in SEG.items():
    v = app[col].astype("object").where(app[col].notna(), "Missing").astype(str)
    if col == "THIN_FILE":
        v = v.map({"True": "No bureau record", "False": "Has bureau record"})
    if col == "CODE_GENDER":
        v = v.map({"F": "Women", "M": "Men"}).fillna("Not recorded")
    if col.startswith("FLAG_OWN_"):
        v = v.map({"Y": "Yes", "N": "No"})
    if col == "REGION_RATING_CLIENT_W_CITY":
        v = "Rating " + v.str.replace(".0", "", regex=False)
    counts = v.value_counts()
    keep_rows = v.isin(counts[counts >= 10].index)                 # 4 'XNA' genders are too few to show
    v, ys = v[keep_rows], y[keep_rows]
    rare = counts[(counts < 500) & (counts >= 10)].index
    v = v.where(~v.isin(rare), "Other (fewer than 500 each)")
    g = ys.groupby(v).agg(["size", "sum", "mean"])
    order = ORDER.get(col, list(g.sort_values("mean", ascending=False).index))
    for i, lvl in enumerate(order):
        r = g.loc[lvl]
        srows.append({"segment": seg, "level": lvl, "order": i, "applicants": int(r["size"]), "defaults": int(r["sum"]),
                      "default_rate": r["mean"], "share": r["size"] / len(app)})
write("segments", srows, "data/interim/application_train (+ bureau for the thin-file flag)")

# ---- distributions: histogram + default rate per bin
DIST = [  # key, label, series, scale, unit
    ("AGE", "Age at application", app.AGE, "linear", "years"),
    ("YEARS_EMPLOYED", "Years in current job (pensioners excluded)", app.YEARS_EMPLOYED, "linear", "years"),
    ("AMT_INCOME_TOTAL", "Income", app.AMT_INCOME_TOTAL, "log", "currency units"),
    ("AMT_CREDIT", "Loan amount", app.AMT_CREDIT, "log", "currency units"),
    ("AMT_ANNUITY", "Loan annuity (instalment)", app.AMT_ANNUITY, "log", "currency units"),
    ("AMT_GOODS_PRICE", "Price of the goods", app.AMT_GOODS_PRICE, "log", "currency units"),
    ("CREDIT_TERM", "Loan term (credit / annuity)", app.CREDIT_TERM, "linear", "months"),
    ("CREDIT_GOODS", "Loan amount / goods price", app.CREDIT_GOODS, "linear", "ratio"),
    ("ANNUITY_INCOME", "Annuity / income", app.ANNUITY_INCOME, "linear", "ratio"),
    ("EXT_SOURCE_1", "External score 1", app.EXT_SOURCE_1, "linear", "score 0-1"),
    ("EXT_SOURCE_2", "External score 2", app.EXT_SOURCE_2, "linear", "score 0-1"),
    ("EXT_SOURCE_3", "External score 3", app.EXT_SOURCE_3, "linear", "score 0-1"),
    ("YEARS_ID_PUBLISH", "Years since ID document issued", -app.DAYS_ID_PUBLISH / 365.25, "linear", "years"),
    ("YEARS_REGISTRATION", "Years since registration changed", -app.DAYS_REGISTRATION / 365.25, "linear", "years"),
    ("YEARS_PHONE_CHANGE", "Years since phone changed (day-0 code excluded)",
     -app.DAYS_LAST_PHONE_CHANGE.where(app.DAYS_LAST_PHONE_CHANGE != 0) / 365.25, "linear", "years"),
    ("OWN_CAR_AGE", "Car age (codes 64/65 excluded)", app.OWN_CAR_AGE.where(~app.OWN_CAR_AGE.isin([64, 65])), "linear", "years"),
    ("REGION_POPULATION_RELATIVE", "Population density of the region", app.REGION_POPULATION_RELATIVE, "linear", "normalised"),
]
drows = []
for key, label, s, scale, unit in DIST:
    s = s.astype("float64")
    miss = s.isna()
    x = s[~miss]
    lo, hi = x.quantile([0.005, 0.995])
    if scale == "log":
        edges = np.geomspace(lo, hi, 21)
    else:
        edges = np.linspace(lo, hi, 21)
    b = np.clip(np.searchsorted(edges, x.clip(lo, hi), side="right") - 1, 0, 19)
    g = y[~miss].groupby(b).agg(["size", "mean"])
    for i in range(20):
        n = int(g["size"].get(i, 0))
        drows.append({"feature": key, "label": label, "scale": scale, "unit": unit, "bin": i, "lo": edges[i], "hi": edges[i + 1],
                      "applicants": n, "default_rate": g["mean"].get(i, np.nan) if n else None,
                      "missing_share": miss.mean(), "missing_default_rate": y[miss].mean() if miss.any() else None,
                      "median": x.median()})
write("distributions", drows, "data/interim/application_train; markers recoded as in the leakage table; "
      "20 bins between the 0.5th and 99.5th percentile (values beyond are counted in the end bins)")

# ---- loan size and term (fifths)
qrows = []
for key, label in [("AMT_CREDIT", "Loan amount"), ("CREDIT_TERM", "Loan term (months)"),
                   ("CREDIT_GOODS", "Loan amount / goods price"), ("ANNUITY_INCOME", "Annuity / income")]:
    q = pd.qcut(app[key], 5, duplicates="drop")
    g = y.groupby(q, observed=True).agg(["size", "mean"])
    w = (y * app.AMT_CREDIT).groupby(q, observed=True).sum() / app.AMT_CREDIT.groupby(q, observed=True).sum()
    for i, (iv, r) in enumerate(g.iterrows()):
        qrows.append({"variable": key, "label": label, "fifth": i + 1, "lo": iv.left, "hi": iv.right,
                      "applicants": int(r["size"]), "default_rate": r["mean"], "default_rate_amount": w.loc[iv]})
write("loan_size_term", qrows, "data/interim/application_train; fifths (quintiles) of each variable")

# ---- missingness (main table)
mrows = []
for c in app.columns[:122]:
    m = app[c].isna()
    if c == "DAYS_EMPLOYED":
        m = app[c] == NO_DATE
    if m.any() and c not in ("SK_ID_CURR", "TARGET"):
        grp = dic[(dic.table == "application_train") & (dic.column == c)].group.iloc[0]
        mrows.append({"column": c, "group": grp, "missing_pct": 100 * m.mean(), "default_if_missing": y[m].mean(),
                      "default_if_present": y[~m].mean(), "missing_in_thin_file_pct": 100 * m[app.THIN_FILE].mean(),
                      "missing_with_bureau_pct": 100 * m[~app.THIN_FILE].mean()})
mrows.sort(key=lambda r: -r["missing_pct"])
write("missingness", mrows, "data/interim/application_train (+ bureau for the thin-file split); DAYS_EMPLOYED counts the 365243 marker as missing")

# ---- strongest signals (training fold)
sh = pd.read_csv("configs/feature_shapes.csv")
blk_label = {"application": "Application form (A)", "application_bureau": "Bureau-derived main-table columns (B)",
             "bureau": "Bureau tables (B)", "previous": "Earlier applications (C)", "installments": "Instalments (C)",
             "pos": "POS / cash loans (C)", "credit_card": "Credit cards (C)"}
sig = sh.head(25).assign(source=lambda d: d.block.map(blk_label))
write("signals", sig[["feature", "block", "source", "iv", "shape", "bin_rates"]].to_dict("records"),
      "configs/feature_shapes.csv (make shapes): training fold, 215,251 applicants")

# ---- thin file
thin = app.THIN_FILE
TF = [("Applicants", lambda m: m.sum(), "count"), ("Default rate", lambda m: y[m].mean(), "share"),
      ("External score 3 missing", lambda m: app.EXT_SOURCE_3[m].isna().mean(), "share"),
      ("Bureau enquiries missing", lambda m: app.AMT_REQ_CREDIT_BUREAU_YEAR[m].isna().mean(), "share"),
      ("External score 1 missing", lambda m: app.EXT_SOURCE_1[m].isna().mean(), "share"),
      ("Under 25", lambda m: (app.AGE[m] < 25).mean(), "share"),
      ("Median age", lambda m: app.AGE[m].median(), "years"),
      ("Revolving loans", lambda m: (app.NAME_CONTRACT_TYPE[m] == "Revolving loans").mean(), "share"),
      ("Median loan amount", lambda m: app.AMT_CREDIT[m].median(), "currency units")]
write("thin_file", [{"metric": n, "has_bureau": f(~thin), "thin_file": f(thin), "format": fm} for n, f, fm in TF],
      "data/interim/application_train, bureau")

# ---- fairness cells
fa = app[app.CODE_GENDER.isin(["F", "M"])]
g = fa.groupby([fa.CODE_GENDER.astype(str), "AGE_BAND"]).TARGET.agg(["size", "mean"]).reset_index()
g["ci95"] = 1.96 * np.sqrt(g["mean"] * (1 - g["mean"]) / g["size"])
write("fairness", [{"gender": {"F": "Women", "M": "Men"}[r.CODE_GENDER], "age_band": r.AGE_BAND,
                    "order": ORDER["AGE_BAND"].index(r.AGE_BAND), "applicants": int(r["size"]), "default_rate": r["mean"],
                    "ci95": r.ci95} for _, r in g.iterrows()], "data/interim/application_train (4 rows with gender XNA left out)")

# ---- results printed by the executed notebook: proxy test (section 7) and adversarial check (section 10)
nb = json.loads(Path("notebooks/01_eda.ipynb").read_text())
out = "\n".join("".join(o.get("text", "")) for c in nb["cells"] if c["cell_type"] == "code" for o in c.get("outputs", []))
num = lambda pat: float(re.search(pat, out).group(1))  # noqa: E731
proxies = [
    {"attribute": "Gender", "measure": "ROC-AUC (0.5 = no information)", "value": num(r"Gender from other columns: ROC-AUC ([\d.]+)"),
     "baseline": 0.5, "strongest_proxies": "Occupation, organisation type, car ownership, income"},
    {"attribute": "Age", "measure": "R² (0 = no information)", "value": num(r"Age from other columns:\s+R² ([\d.]+)"),
     "baseline": 0.0, "strongest_proxies": "Pension status (FLAG_EMP_PHONE), document 6, external score 1, children"},
]
write("proxies", proxies, "notebooks/01_eda.ipynb, section 7 (executed output): gradient boosting on the other main-table columns, 80,000 applicants, 3-fold")

# ---- drift: training file vs Kaggle test
term_tr, term_te = app.CREDIT_TERM, te.AMT_CREDIT / te.AMT_ANNUITY
DR = [("Model separating the two files (ROC-AUC)", num(r"ROC-AUC train vs Kaggle test.*?: ([\d.]+)"), None, "auc"),
      ("Revolving loans", (app.NAME_CONTRACT_TYPE == "Revolving loans").mean(), (te.NAME_CONTRACT_TYPE == "Revolving loans").mean(), "share"),
      ("Median loan term (months)", term_tr.median(), term_te.median(), "number"),
      ("Loans under 12 months", (term_tr < 12).mean(), (term_te < 12).mean(), "share"),
      ("Median loan amount", app.AMT_CREDIT.median(), te.AMT_CREDIT.median(), "number"),
      ("Median annuity", app.AMT_ANNUITY.median(), te.AMT_ANNUITY.median(), "number"),
      ("Any bureau enquiry in the last month", (app.AMT_REQ_CREDIT_BUREAU_MON > 0).mean(), (te.AMT_REQ_CREDIT_BUREAU_MON > 0).mean(), "share"),
      ("Any bureau enquiry in the last quarter", (app.AMT_REQ_CREDIT_BUREAU_QRT > 0).mean(), (te.AMT_REQ_CREDIT_BUREAU_QRT > 0).mean(), "share"),
      ("Women", (app.CODE_GENDER == "F").mean(), (te.CODE_GENDER == "F").mean(), "share")]
write("drift", [{"metric": n, "training": a, "kaggle_test": b, "format": f} for n, a, b, f in DR],
      "data/interim/application_train, application_test; separation ROC-AUC from notebooks/01_eda.ipynb section 10")

# ---- data quality and leakage findings
inst = rd("installments_payments", ["SK_ID_PREV", "NUM_INSTALMENT_VERSION", "NUM_INSTALMENT_NUMBER"])
split_keys = int(inst.duplicated(["SK_ID_PREV", "NUM_INSTALMENT_VERSION", "NUM_INSTALMENT_NUMBER"]).sum())  # repeats after the first
del inst
prev = rd("previous_application", ["AMT_CREDIT"])
person = app.groupby(["CODE_GENDER", "DAYS_BIRTH", "DAYS_ID_PUBLISH", "DAYS_REGISTRATION"], observed=True).SK_ID_CURR.transform("size")
Q = [("Placeholder", "DAYS_EMPLOYED = 365243 (pensioners, unemployed)", (app.DAYS_EMPLOYED == NO_DATE).sum(), "Missing + flag"),
     ("Placeholder", "OWN_CAR_AGE = 64 or 65", app.OWN_CAR_AGE.isin([64, 65]).sum(), "Missing + flag"),
     ("Placeholder", "DAYS_LAST_PHONE_CHANGE = 0", (app.DAYS_LAST_PHONE_CHANGE == 0).sum(), "Missing + flag"),
     ("Outlier", "Income above 1,000,000 (max 117,000,000)", (app.AMT_INCOME_TOTAL > 1e6).sum(), "Cap at training 99.9th percentile"),
     ("Leakage", "Bureau rows updated after the application", (bur.DAYS_CREDIT_UPDATE > 0).sum(), "Rows dropped"),
     ("Error", "Bureau dates about 110 years ago", (bur.DAYS_CREDIT_ENDDATE < -40000).sum() + (bur.DAYS_CREDIT_UPDATE < -40000).sum() + (bur.DAYS_ENDDATE_FACT < -40000).sum(), "Missing"),
     ("Error", "Bureau credits that end before they start", (bur.DAYS_ENDDATE_FACT < bur.DAYS_CREDIT).sum(), "Missing end date"),
     ("Structure", "Instalment rows repeating a key (split payments)", split_keys, "Summed per instalment"),
     ("Structure", "Earlier applications with AMT_CREDIT = 0", (prev.AMT_CREDIT == 0).sum(), "Amounts of approved ones only"),
     ("Structure", "Applications from people with two IDs", (person > 1).sum(), "Split keeps each person in one fold"),
     ("Low signal", "Near-constant flags (fewer than 100 rows differ)", 7, "Dropped")]
write("quality", [{"type": a, "issue": b, "rows": int(c), "handling": d} for a, b, c, d in Q],
      "data/interim/application_train, bureau, previous_application, installments_payments")
