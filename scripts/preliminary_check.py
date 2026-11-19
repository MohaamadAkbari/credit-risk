"""Preliminary check (17-19 Nov 2026): rough profit comparison on the main table only.
Exploration, not the official baseline. Replaced by the tested pipeline in Phase 3.

19 Nov (Phase 2 review, finding 1; ADR 0003): profit is reported three ways:
  unit    every loan counts as 1 (the original measure)
  amount  each loan weighted by AMT_CREDIT: profit per 1,000 of principal applied for (primary, D54)
  term    amount-weighted, with a margin that grows with the loan term (sensitivity E6)
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
be = m / (m + L)             # break-even PD (the same for every loan when margin and loss scale with the amount)
amt = a.loc[Xte.index, 'AMT_CREDIT'].to_numpy()
n_inst = (a.AMT_CREDIT / a.AMT_ANNUITY).loc[Xte.index].to_numpy()          # term in months, roughly
# Term-scaled margin: annual margin x years x average outstanding share of an equal-instalment loan
m_term = m * (n_inst / 12) * (n_inst + 1) / (2 * n_inst)
m_term = np.where(np.isfinite(m_term), m_term, m)                         # 12 loans without an annuity: flat margin
print(f'term-scaled margin: median {np.median(m_term):.3f}, 5-95% {np.quantile(m_term, .05):.3f}-{np.quantile(m_term, .95):.3f}, '
      f'amount-weighted mean {np.average(m_term, weights=amt):.3f}')


def profit(approve, y, weight='unit', margin=m):
    w = np.ones(len(y)) if weight == 'unit' else amt
    return 1000 * np.sum(w * approve * ((1 - y) * margin - y * L)) / np.sum(w)


def report(label, ap, y, base):
    print(f'  {label}: decline {1-ap.mean():.1%} (amount {1-np.average(ap, weights=amt):.1%}), '
          f'default among approved {y[ap==1].mean():.2%} (amount-weighted {np.average(y[ap==1], weights=amt[ap==1]):.2%})')
    for k, (w, mg) in {'unit': ('unit', m), 'amount': ('amount', m), 'term': ('amount', m_term)}.items():
        pr = profit(ap, y, w, mg)
        print(f'    profit [{k:>6}] {pr:6.1f} ({pr/base[k]-1:+.1%} vs approve everyone)')


ones = np.ones(len(yte))
base = {'unit': profit(ones, yte), 'amount': profit(ones, yte, 'amount'), 'term': profit(ones, yte, 'amount', m_term)}
print('approve everyone: profit per 1,000 =', {k: round(v, 1) for k, v in base.items()},
      '| default rate', round(yte.mean(), 4), '| amount-weighted', round(np.average(yte, weights=amt), 4))
models = {
 'logistic (scorecard-like)': make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),
                                            LogisticRegression(max_iter=500)).fit(Xtr, ytr),
 'gradient boosting': HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, random_state=0).fit(Xtr, ytr)}
out = {}
for name, mod in models.items():
    p = mod.predict_proba(Xte)[:, 1]
    print(f'\n{name}: ROC-AUC {roc_auc_score(yte, p):.3f}')
    ap = (p < be).astype(float)
    report(f'break-even cutoff {be:.3f}', ap, yte, base)
    ap_t = (p < m_term / (m_term + L)).astype(float)             # per-loan break-even under the term-scaled margin
    pr_t = profit(ap_t, yte, 'amount', m_term)
    print(f'  term-scaled break-even (per loan): decline {1-ap_t.mean():.1%}, profit [  term] {pr_t:.1f} '
          f'({pr_t/base["term"]-1:+.1%})')
    out[name] = ({k: profit(ap, yte, *(('unit', m), ('amount', m), ('amount', m_term))[i])
                  for i, k in enumerate(base)}, p)
    for cap in (0.05, 0.10, 0.15):
        ap2 = (p < np.quantile(p, 1 - cap)).astype(float)
        print(f'  decline riskiest {cap:.0%}: approved default rate {yte[ap2==1].mean():.2%}, '
              f'profit unit {profit(ap2, yte)/base["unit"]-1:+.1%}, amount {profit(ap2, yte, "amount")/base["amount"]-1:+.1%}, '
              f'defaults caught {yte[ap2==0].sum()/yte.sum():.1%}')
g_, l_ = out['gradient boosting'][0], out['logistic (scorecard-like)'][0]
print('\ngradient boosting vs logistic:', {k: f'{g_[k]/l_[k]-1:+.1%}' for k in base})
p = out['gradient boosting'][1]
ap = p < be
g = a.loc[Xte.index, 'CODE_GENDER'].values
for gg in ('F', 'M'):
    mk = g == gg
    print(gg, 'approval', round(ap[mk].mean(), 3), '| approval among people who repay', round(ap[mk & (yte == 0)].mean(), 3))
