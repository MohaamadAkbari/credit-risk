"""The split: shares, stratification, disjoint folds and a stable fingerprint."""
import numpy as np
import pandas as pd

from credit_risk.data.split import PERSON_KEY, SHARES, fingerprint, make_split, manifest


def _labels(n=20_000, rate=0.08, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"SK_ID_CURR": np.arange(100_000, 100_000 + n), "TARGET": (rng.random(n) < rate).astype(int)})


def test_shares_and_stratification():
    s = make_split(_labels())
    for fold, share in SHARES.items():
        part = s[s.fold == fold]
        assert abs(len(part) / len(s) - share) < 0.002
        assert abs(part.TARGET.mean() - s.TARGET.mean()) < 0.003


def test_folds_are_disjoint_and_complete():
    lab = _labels()
    s = make_split(lab)
    assert s.SK_ID_CURR.is_unique and len(s) == len(lab)


def test_same_seed_same_test_set():
    lab = _labels()
    assert manifest(make_split(lab)) == manifest(make_split(lab.sample(frac=1, random_state=1)))
    a, b = make_split(lab), make_split(lab, seed=7)
    assert fingerprint(a[a.fold == "test"].SK_ID_CURR) != fingerprint(b[b.fold == "test"].SK_ID_CURR)


def test_same_person_stays_in_one_fold():
    lab = _labels(n=2_000)
    rng = np.random.default_rng(3)
    for c in PERSON_KEY:
        lab[c] = rng.integers(0, 10**9, len(lab))
    twins = lab.sample(300, random_state=0).index
    copies = lab.loc[twins].assign(SK_ID_CURR=lab.SK_ID_CURR.max() + 1 + np.arange(len(twins)))  # same person, new ID
    both = pd.concat([lab, copies], ignore_index=True)
    s = make_split(both).set_index("SK_ID_CURR").fold
    assert (s.loc[lab.loc[twins, "SK_ID_CURR"]].to_numpy() == s.loc[copies.SK_ID_CURR].to_numpy()).all()
    assert len(s) == len(both)
