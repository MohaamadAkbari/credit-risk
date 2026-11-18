"""Convert the raw Home Credit CSVs to compact Parquet files (raw -> interim).

The raw CSVs stay untouched. IDs become int32 and every other number float32, so that the
large tables fit in a few GB of memory. Text columns become pandas strings.
Big tables are read in chunks. Nothing is cleaned or recoded here: that is Phase 3.

Usage: python -m credit_risk.data.interim [RAW_DIR] [OUT_DIR]   (or: make interim)
"""
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

TABLES = ["application_train", "application_test", "bureau", "bureau_balance",
          "previous_application", "POS_CASH_balance", "installments_payments",
          "credit_card_balance"]
ID_COLS = {"SK_ID_CURR", "SK_ID_PREV", "SK_ID_BUREAU"}


def shrink(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        s = df[c]
        if c in ID_COLS:
            df[c] = s.astype("int32")
        elif pd.api.types.is_numeric_dtype(s):
            # One fixed type for every chunk. float32 keeps ~7 significant digits:
            # fine for exploration, but Phase 3 features are built from the raw CSVs.
            df[c] = s.astype("float32")
        elif s.dtype == "object":
            df[c] = s.astype("string")
    return df


def convert(src: Path, dst: Path, name: str, chunksize: int = 1_000_000) -> None:
    out = dst / f"{name}.parquet"
    if out.exists():
        print("exists", out)
        return
    writer, rows, schema = None, 0, None
    for chunk in pd.read_csv(src / f"{name}.csv", chunksize=chunksize, low_memory=False):
        chunk = shrink(chunk)
        table = pa.Table.from_pandas(chunk, preserve_index=False)
        if writer is None:
            schema = table.schema
            writer = pq.ParquetWriter(out, schema, compression="zstd")
        else:
            table = table.cast(schema)   # keep the first chunk's types
        writer.write_table(table)
        rows += len(chunk)
    writer.close()
    print(f"{name}: {rows:,} rows -> {out}")


def main(argv: list[str] | None = None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw", nargs="?", default="data/home-credit-default-risk", type=Path)
    ap.add_argument("out", nargs="?", default="data/interim", type=Path)
    ap.add_argument("--tables", nargs="*", default=TABLES)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for t in args.tables:
        convert(args.raw, args.out, t)


if __name__ == "__main__":
    main()
