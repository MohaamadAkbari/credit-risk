"""Preliminary check (17-18 Nov 2026): rough profit comparison on the main table only.
Exploration, not the official baseline. Replaced by the tested pipeline in Phase 3.
Usage: python scripts/preliminary_check.py data/home-credit-default-risk   (or: make preliminary)
"""
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

a = pd.read_csv(sys.argv[1] + '/application_train.csv')
a['DAYS_EMPLOYED'] = a['DAYS_EMPLOYED'].replace(365243, np.nan)   # no-date marker
feats = ['EXT_SOURCE_1', 'EXT_SOURCE_2', 'EXT_SOURCE_3', 'AMT_INCOME_TOTAL', 'AMT_CREDIT', 'AMT_ANNUITY',
         'AMT_GOODS_PRICE', 'DAYS_EMPLOYED', 'DAYS_ID_PUBLISH', 'DAYS_REGISTRATION', 'CNT_CHILDREN',
         'CNT_FAM_MEMBERS', 'REGION_POPULATION_RELATIVE', 'OWN_CAR_AGE']   # no gender, no age
X = a[feats].copy()
X['CREDIT_INCOME'] = a.AMT_CREDIT / a.AMT_INCOME_TOTAL
X['ANNUITY_INCOME'] = a.AMT_ANNUITY / a.AMT_INCOME_TOTAL
X['REVOLVING'] = (a.NAME_CONTRACT_TYPE == 'Revolving loans').astype(int)
y = a.TARGET.values
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)

m, L = 0.12, 0.60            # placeholders from configs/economics.yaml
be = m / (m + L)             # break-even PD
def profit(approve, y):      # per 1,000 applicants, loan size = 1
    return 1000 * np.mean(approve * ((1 - y) * m - y * L))

base = profit(np.ones(len(yte)), yte)
print('approve everyone: profit per 1,000 =', round(base, 1), '| default rate', round(yte.mean(), 4))
models = {
 'logistic (scorecard-like)': make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),
                                            LogisticRegression(max_iter=500)).fit(Xtr, ytr),
 'gradient boosting': HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, random_state=0).fit(Xtr, ytr)}
out = {}
for name, mod in models.items():
    p = mod.predict_proba(Xte)[:, 1]
    print(f'\n{name}: ROC-AUC {roc_auc_score(yte, p):.3f}')
    ap = (p < be).astype(float)
    pr = profit(ap, yte)
    out[name] = (pr, p)
    print(f'  break-even cutoff {be:.3f}: decline {1-ap.mean():.1%}, default rate among approved {yte[ap==1].mean():.2%}, '
          f'profit {pr:.1f} ({pr/base-1:+.1%} vs approve everyone)')
    for cap in (0.05, 0.10, 0.15):
        ap2 = (p < np.quantile(p, 1 - cap)).astype(float)
        pr2 = profit(ap2, yte)
        print(f'  decline riskiest {cap:.0%}: approved default rate {yte[ap2==1].mean():.2%}, profit {pr2:.1f} '
              f'({pr2/base-1:+.1%}), defaults caught {yte[ap2==0].sum()/yte.sum():.1%}')
print('\ngradient boosting vs logistic:', f"{out['gradient boosting'][0]/out['logistic (scorecard-like)'][0]-1:+.1%}")
p = out['gradient boosting'][1]
ap = p < be
g = a.loc[Xte.index, 'CODE_GENDER'].values
for gg in ('F', 'M'):
    mk = g == gg
    print(gg, 'approval', round(ap[mk].mean(), 3), '| approval among people who repay', round(ap[mk & (yte == 0)].mean(), 3))
