"""Read interim tables with only the columns a step declares."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load(interim: Path, table: str, columns: list[str] | None = None) -> pd.DataFrame:
    """Read one interim Parquet table. Text columns become categories to save memory."""
    df = pd.read_parquet(Path(interim) / f"{table}.parquet", columns=columns)
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_string_dtype(s) and not isinstance(s.dtype, pd.CategoricalDtype):
            df[c] = s.astype("category")
    return df
