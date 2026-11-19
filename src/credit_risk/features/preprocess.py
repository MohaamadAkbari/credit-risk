"""Preprocessing that learns from data, so it is fitted on the training fold only (D21).

make_preprocessor(X) returns an unfitted scikit-learn ColumnTransformer:
  numbers     -> cap at the training 0.1% / 99.9% quantiles -> median imputation + missing flags (D39)
                 -> optional standard scaling (for linear models)
  categories  -> "MISSING" for empty values (D39) -> one-hot, levels rarer than min_frequency
                 in training grouped as "infrequent", unseen levels mapped there too
Put it in a Pipeline with the model, so training and scoring share one code path.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler


class QuantileClipper(BaseEstimator, TransformerMixin):
    """Clip each column to quantiles learned in fit (e.g. the 117,000,000 income)."""

    def __init__(self, lower: float = 0.001, upper: float = 0.999):
        self.lower, self.upper = lower, upper

    def fit(self, X, y=None):
        a = np.asarray(X, dtype="float64")
        self.n_features_in_ = a.shape[1]
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        with np.errstate(all="ignore"):
            self.lower_ = np.nanquantile(a, self.lower, axis=0)
            self.upper_ = np.nanquantile(a, self.upper, axis=0)
        return self

    def transform(self, X):
        a = np.asarray(X, dtype="float64")
        return np.clip(a, self.lower_, self.upper_)

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.asarray(input_features, dtype=object)
        return getattr(self, "feature_names_in_", np.asarray([f"x{i}" for i in range(self.n_features_in_)], dtype=object))


def _as_object(X):
    return pd.DataFrame(X).astype(object)


def make_preprocessor(X: pd.DataFrame, scale: bool = False, min_frequency: int = 50) -> ColumnTransformer:
    num = list(X.select_dtypes("number").columns)
    cat = [c for c in X.columns if c not in num]
    num_steps = [("clip", QuantileClipper()), ("impute", SimpleImputer(strategy="median", add_indicator=True))]
    if scale:
        num_steps.append(("scale", StandardScaler()))
    cat_steps = [("as_object", FunctionTransformer(_as_object, feature_names_out="one-to-one")),
                 ("impute", SimpleImputer(strategy="constant", fill_value="MISSING")),
                 ("onehot", OneHotEncoder(min_frequency=min_frequency, handle_unknown="infrequent_if_exist",
                                          sparse_output=False))]
    return ColumnTransformer([("num", Pipeline(num_steps), num), ("cat", Pipeline(cat_steps), cat)],
                             verbose_feature_names_out=False)
