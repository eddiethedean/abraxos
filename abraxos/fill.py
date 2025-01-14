import typing as t

import pandas as pd


def fill_nans(d: dict, fill: t.Any) -> dict:
    return {col: fill if pd.isna(val) else val for col, val in d.items()}