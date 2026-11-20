"""The preprocessor learns caps and category levels from the data it is fitted on, and nothing else."""
import numpy as np
import pandas as pd

from credit_risk.features.preprocess import QuantileClipper, make_preprocessor


def _frame(n=1000, seed=0):
    rng = np.random.default_rng(seed)
    income = rng.normal(100, 10, n)
    income[0] = 1e6                                            # an outlier, like the 117,000,000 income
    occ = rng.choice(["a", "b", "c"], n).astype(object)
    occ[:100] = None                                           # common enough (>= 50) to keep its own level
    occ[100:102] = "rare"                                      # too rare: grouped as infrequent
    return pd.DataFrame({"INCOME": income, "SCORE": np.where(rng.random(n) < 0.2, np.nan, rng.random(n)),
                         "OCCUPATION": pd.Categorical(occ)})


def test_clipper_uses_fitted_quantiles_only():
    train = pd.DataFrame({"x": np.arange(1000.0)})
    c = QuantileClipper(0.01, 0.99).fit(train)
    out = c.transform(pd.DataFrame({"x": [-50.0, 5000.0]}))
    assert out[0, 0] == c.lower_[0] and out[1, 0] == c.upper_[0]


def test_output_has_no_missing_and_flags_missingness():
    X = _frame()
    pre = make_preprocessor(X).fit(X)
    out = pd.DataFrame(pre.transform(X), columns=pre.get_feature_names_out())
    assert not out.isna().any().any()
    assert "missingindicator_SCORE" in out.columns
    assert out.INCOME.max() < 1e6                              # outlier capped
    assert "OCCUPATION_MISSING" in out.columns and "OCCUPATION_infrequent_sklearn" in out.columns


def test_unseen_category_at_scoring_time_does_not_fail():
    X = _frame()
    pre = make_preprocessor(X).fit(X)
    new = X.head(2).copy()
    new["OCCUPATION"] = pd.Categorical(["never seen", "a"])
    assert pre.transform(new).shape[0] == 2


def test_fit_on_train_only_changes_with_the_fit_data():
    X = _frame()
    a = make_preprocessor(X).fit(X.iloc[:500])
    b = make_preprocessor(X).fit(X.iloc[500:])
    clip_a = a.named_transformers_["num"].named_steps["clip"].upper_
    clip_b = b.named_transformers_["num"].named_steps["clip"].upper_
    assert not np.allclose(clip_a, clip_b)
