"""Unit tests for the raw -> interim conversion (no data needed)."""
import pandas as pd

from credit_risk.data.interim import convert, shrink


def test_shrink_types():
    df = pd.DataFrame({"SK_ID_CURR": [100002, 100003], "AMT_CREDIT": [1.5, None],
                       "CNT_CHILDREN": [0, 2], "NAME_CONTRACT_TYPE": ["Cash loans", None]})
    out = shrink(df.copy())
    assert str(out.SK_ID_CURR.dtype) == "int32"
    assert str(out.AMT_CREDIT.dtype) == "float32"
    assert str(out.CNT_CHILDREN.dtype) == "float32"
    assert str(out.NAME_CONTRACT_TYPE.dtype) == "string"
    assert out.AMT_CREDIT.isna().sum() == 1


def test_convert_round_trip_across_chunks(tmp_path):
    raw, dst = tmp_path / "raw", tmp_path / "interim"
    raw.mkdir()
    dst.mkdir()
    df = pd.DataFrame({"SK_ID_CURR": range(10), "AMT": [float(i) for i in range(10)],
                       "CAT": ["a", "b"] * 5})
    df.to_csv(raw / "toy.csv", index=False)
    convert(raw, dst, "toy", chunksize=3)          # four chunks, one schema
    back = pd.read_parquet(dst / "toy.parquet")
    assert len(back) == 10
    assert back.SK_ID_CURR.tolist() == list(range(10))
    assert back.AMT.sum() == 45
