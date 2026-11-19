"""Manager review of Phase 2 (19 Nov 2026): checks the EDA did not run.

Every number in docs/04_manager_review_phase2.md and in section 10 of notebooks/01_eda.ipynb
comes from this script. Like the rest of the EDA it describes all labelled applications; the
modelling choices that follow from it (feature shapes) use the training fold only.
Usage: python3 scripts/phase2_review_checks.py [data/interim]   (or: make checks)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

D = Path(sys.argv[1] if len(sys.argv) > 1 else "data/interim")


def rd(table, cols=None):
    return pd.read_parquet(D / f"{table}.parquet", columns=cols)


def auc(score, y):
    m = score.notna()
    s, t = score[m].to_numpy(), y[m].to_numpy()
    r = rankdata(s)
    n1 = t.sum()
    n0 = len(t) - n1
    a = (r[t == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    return round(max(a, 1 - a), 3), int(m.sum())


def by_quintile(df, col):
    q = pd.qcut(df[col], 5, duplicates="drop")
    return df.groupby(q, observed=True).TARGET.agg(["size", "mean"]).round(3)


app = rd("application_train")
te = rd("application_test")
bur_ids = rd("bureau", ["SK_ID_CURR"]).SK_ID_CURR
app["THIN"] = ~app.SK_ID_CURR.isin(bur_ids)
app["TERM"] = app.AMT_CREDIT / app.AMT_ANNUITY
app["ANNUITY_INCOME"] = app.AMT_ANNUITY / app.AMT_INCOME_TOTAL
app["CREDIT_GOODS"] = app.AMT_CREDIT / app.AMT_GOODS_PRICE
app["EXT_MEAN"] = app[["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]].mean(axis=1)

print("\n## 1. Loan size, term and the profit unit")
print("count default rate", round(app.TARGET.mean(), 4),
      "| amount-weighted", round((app.TARGET * app.AMT_CREDIT).sum() / app.AMT_CREDIT.sum(), 4))
for c in ["AMT_CREDIT", "TERM", "CREDIT_GOODS", "ANNUITY_INCOME"]:
    print(c)
    print(by_quintile(app, c))
print("TERM (months) 5/25/50/75/95%:", app.TERM.quantile([.05, .25, .5, .75, .95]).round(1).tolist())
print("AMT_GOODS_PRICE missing by contract:",
      app.AMT_GOODS_PRICE.isna().groupby(app.NAME_CONTRACT_TYPE).sum().to_dict())

print("\n## 2. Thin file vs the strongest signals")
t = app.groupby("THIN").agg(
    n=("TARGET", "size"), default=("TARGET", "mean"),
    ext1_missing=("EXT_SOURCE_1", lambda s: s.isna().mean()),
    ext3_missing=("EXT_SOURCE_3", lambda s: s.isna().mean()),
    req_bureau_missing=("AMT_REQ_CREDIT_BUREAU_YEAR", lambda s: s.isna().mean()),
    under_25=("DAYS_BIRTH", lambda s: (-s / 365.25 < 25).mean()))
print(t.round(3).T)
for c in ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3", "EXT_MEAN"]:
    print(c, "thin", auc(app[c][app.THIN], app.TARGET[app.THIN]),
          "has bureau", auc(app[c][~app.THIN], app.TARGET[~app.THIN]))

print("\n## 3. Same person under several application IDs")
key = ["CODE_GENDER", "DAYS_BIRTH", "DAYS_ID_PUBLISH", "DAYS_REGISTRATION"]
size = app.groupby(key).SK_ID_CURR.transform("size")
grp = app[size > 1].groupby(key).TARGET.agg(["size", "mean"])
print("rows", int((size > 1).sum()), "groups", len(grp),
      "groups with mixed outcomes", int(((grp["mean"] > 0) & (grp["mean"] < 1)).sum()))
split = Path(D).parent / "processed" / "split.parquet"
if split.exists():
    m = app[key + ["SK_ID_CURR"]].merge(pd.read_parquet(split, columns=["SK_ID_CURR", "fold"]), on="SK_ID_CURR")
    g = m.groupby(key).fold.agg(["size", "nunique"])
    g = g[g["size"] > 1]
    print("groups spanning more than one fold", int((g["nunique"] > 1).sum()))

print("\n## 4. Unexamined codes and process fields")
print("OWN_CAR_AGE 60-70:", app.OWN_CAR_AGE.value_counts().sort_index().loc[60:70].to_dict())
z = app.DAYS_LAST_PHONE_CHANGE == 0
print("DAYS_LAST_PHONE_CHANGE == 0:", int(z.sum()), "default", round(app.TARGET[z].mean(), 3),
      "| rows at -1:", int((app.DAYS_LAST_PHONE_CHANGE == -1).sum()))
e2 = app.EXT_SOURCE_2
print("EXT_SOURCE_2 < 0.001:", int((e2 < 0.001).sum()), "default", round(app.TARGET[e2 < 0.001].mean(), 3),
      "| counts in [0, .0001, .001, .002, .005, .01):", np.histogram(e2.dropna(), [0, .0001, .001, .002, .005, .01])[0].tolist())
h = app.groupby("HOUR_APPR_PROCESS_START").TARGET.agg(["size", "mean"]).round(3)
print("default by hour (n > 1,000):")
print(h[h["size"] > 1000].T.to_string())
r = app.REGION_RATING_CLIENT_W_CITY
hb = pd.cut(app.HOUR_APPR_PROCESS_START, [-1, 7, 11, 15, 24], labels=["<=7", "8-11", "12-15", "16+"])
print("share starting by 7 am, by region rating:", (hb == "<=7").groupby(r).mean().round(3).to_dict())
print("default by hour band within region rating:")
print(app.pivot_table(index=r, columns=hb, values="TARGET", aggfunc="mean", observed=True).round(3))
print("FLAG_EMP_PHONE vs DAYS_EMPLOYED = 365243:")
print(pd.crosstab(app.FLAG_EMP_PHONE, app.DAYS_EMPLOYED == 365243))

print("\n## 5. Redundant pairs (|r| > 0.95, building _MODE/_MEDI excluded)")
num = app.select_dtypes("number").drop(columns=["SK_ID_CURR", "TARGET"])
num = num[[c for c in num if not c.endswith(("_MODE", "_MEDI"))]]
cm = num.corr().abs()
pairs = cm.where(np.triu(np.ones(cm.shape, bool), 1)).stack()
print(pairs[pairs > 0.95].round(3))

print("\n## 6. Is the application ID a hidden time order?")
q = pd.qcut(app.SK_ID_CURR, 10)
print("default by ID decile", app.groupby(q, observed=True).TARGET.mean().round(4).tolist())
print("EXT_SOURCE_3 mean by ID decile", app.groupby(q, observed=True).EXT_SOURCE_3.mean().round(3).tolist())

print("\n## 7. Earlier applications that look like the current one")
prev = rd("previous_application", ["SK_ID_CURR", "NAME_CONTRACT_STATUS", "DAYS_DECISION",
                                   "AMT_CREDIT", "AMT_ANNUITY", "DAYS_FIRST_DUE"])
m = prev.merge(app[["SK_ID_CURR", "AMT_CREDIT", "AMT_ANNUITY"]], on="SK_ID_CURR", suffixes=("", "_cur"))
same = m[(m.AMT_CREDIT.round() == m.AMT_CREDIT_cur.round()) & (m.AMT_ANNUITY.round() == m.AMT_ANNUITY_cur.round())]
print("same amount and annuity as current:", same.SK_ID_CURR.nunique(), "applicants",
      same.NAME_CONTRACT_STATUS.value_counts().to_dict())
ra = m[(m.DAYS_DECISION >= -7) & (m.NAME_CONTRACT_STATUS == "Approved")]
del m
print("approved in the 7 days before:", ra.SK_ID_CURR.nunique(), "applicants; default",
      round(app.TARGET[app.SK_ID_CURR.isin(ra.SK_ID_CURR)].mean(), 3),
      "; not yet started", round((ra.DAYS_FIRST_DUE == 365243).mean(), 3))

print("\n## 8. Fairness cells: gender x age band, with 95% margin")
app["AGE_BAND"] = pd.cut(-app.DAYS_BIRTH / 365.25, [18, 25, 35, 45, 55, 65, 75], right=False)
c = app[app.CODE_GENDER != "XNA"].groupby(["CODE_GENDER", "AGE_BAND"], observed=True).TARGET.agg(["size", "mean"])
c["pm95"] = 1.96 * np.sqrt(c["mean"] * (1 - c["mean"]) / c["size"])
print(c.round(3))

print("\n## 9. Kaggle test vs train: can a model tell them apart? (adversarial check)")
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.model_selection import cross_val_predict, train_test_split  # noqa: E402

cols = [c for c in te.columns if c != "SK_ID_CURR"]
tr_s = app[cols].sample(100_000, random_state=0)
X = pd.concat([tr_s, te[cols]], ignore_index=True)
for c in X.columns:
    if not pd.api.types.is_numeric_dtype(X[c]):
        v = X[c].astype(object)
        X[c] = pd.Categorical(v.where(v.notna(), None))          # pandas NA -> None so sklearn sees one type
y_t = np.r_[np.zeros(len(tr_s)), np.ones(len(te))]
clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, categorical_features="from_dtype", random_state=0)
p = cross_val_predict(clf, X, y_t, cv=3, method="predict_proba")[:, 1]
print("ROC-AUC train vs Kaggle test (0.5 = indistinguishable):", auc(pd.Series(p), pd.Series(y_t.astype(int)))[0])
Xa, Xb, ya, yb = train_test_split(X, y_t, test_size=20_000, stratify=y_t, random_state=0)
clf.fit(Xa, ya)
imp = permutation_importance(clf, Xb, yb, scoring="roc_auc", n_repeats=3, random_state=0)
top = pd.Series(imp.importances_mean, index=X.columns).sort_values(ascending=False).head(8).round(4)
print("columns that tell them apart (drop in ROC-AUC when shuffled):")
print(top.to_string())
for c in top.index[:5]:
    a_, b_ = app[c], te[c]
    if pd.api.types.is_numeric_dtype(a_):
        print(f"  {c}: train median {a_.median():g} / missing {a_.isna().mean():.1%}; "
              f"test median {b_.median():g} / missing {b_.isna().mean():.1%}")
    else:
        print(f"  {c}: train {a_.value_counts(normalize=True).head(3).round(3).to_dict()}; "
              f"test {b_.value_counts(normalize=True).head(3).round(3).to_dict()}")
term_tr, term_te = app.AMT_CREDIT / app.AMT_ANNUITY, te.AMT_CREDIT / te.AMT_ANNUITY
print("loan term (credit / annuity, months) median train", round(term_tr.median(), 1), "test", round(term_te.median(), 1),
      "| share under 12 months: train", round((term_tr < 12).mean(), 3), "test", round((term_te < 12).mean(), 3))
cash = app.NAME_CONTRACT_TYPE == "Cash loans"
print("cash loans only, term median train", round(term_tr[cash].median(), 1),
      "test", round(term_te[te.NAME_CONTRACT_TYPE == "Cash loans"].median(), 1))
for c in ["AMT_REQ_CREDIT_BUREAU_MON", "AMT_REQ_CREDIT_BUREAU_QRT"]:
    print(f"{c} share > 0: train {(app[c] > 0).mean():.3f}, test {(te[c] > 0).mean():.3f}")
