"""Shape labels used for monotone constraints and scorecard bins (credit_risk.features.shapes)."""
import numpy as np
import pandas as pd

from credit_risk.features.shapes import analyse, shape_of


def test_shape_labels():
    assert shape_of(np.array([.02, .04, .06, .08, .10]), 0.3)[0] == "up"
    assert shape_of(np.array([.10, .08, .06, .04, .02]), 0.3)[0] == "down"
    assert shape_of(np.array([.05, .08, .11, .08, .05]), 0.1)[0] == "hump"
    assert shape_of(np.array([.10, .06, .03, .06, .10]), 0.1)[0] == "U"
    assert shape_of(np.array([.05, .12, .06, .14, .05]), 0.1)[0] == "irregular"   # zig-zag, more than one turn
    assert shape_of(np.array([.05, .12, .06, .14, .05]), 0.01)[0] == "none"       # too little signal


def test_analyse_finds_a_rising_risk_and_counts_missing_as_a_bin():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.random(20_000))
    y = pd.Series((rng.random(20_000) < 0.02 + 0.2 * x).astype(int))
    x[:2_000] = np.nan
    r = analyse(x, y)
    assert r["shape"] == "up" and r["monotone"] == 1 and r["iv"] > 0.1 and r["missing_pct"] == 10.0
