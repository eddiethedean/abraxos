"""Utility functions for DataFrame operations."""

from __future__ import annotations

from collections.abc import Iterator
from operator import index
from typing import Any

import pandas as pd

__all__ = ['split', 'clear', 'to_records']


def _partition_bounds(size: int, count: int) -> Iterator[tuple[int, int]]:
    width, remainder = divmod(size, count)
    start = 0
    for part in range(count):
        stop = start + width + (part < remainder)
        yield start, stop
        start = stop


def split(df: pd.DataFrame, i: int = 2) -> tuple[pd.DataFrame, ...]:
    """
    Splits a DataFrame into `i` approximately equal, independently assignable parts.

    Nested Python objects stored in cells are shared, as with `DataFrame.copy()`.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to be split.
    i : int, optional
        The number of parts to split the DataFrame into (default is 2).

    Returns
    -------
    tuple of pd.DataFrame
        A tuple containing `i` DataFrames, each being a partition of the original DataFrame.

    Examples
    --------
    >>> import pandas as pd
    >>> from abraxos import split
    >>> df = pd.DataFrame({'A': range(10)})
    >>> [part['A'].tolist() for part in split(df, 3)]
    [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]]
    """
    count = index(i)
    if count < 1:
        raise ValueError('i must be at least 1')
    return tuple(df.iloc[start:stop].copy() for start, stop in _partition_bounds(len(df), count))


def clear(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns an empty DataFrame with the same schema (columns and dtypes) as the input.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame.

    Returns
    -------
    pd.DataFrame
        An empty DataFrame with the same structure as `df`.

    Examples
    --------
    >>> import pandas as pd
    >>> from abraxos import clear
    >>> df = pd.DataFrame({'x': [1, 2, 3]})
    >>> clear(df).shape
    (0, 1)
    """
    return df.iloc[:0]


def to_records(df: pd.DataFrame) -> list[dict[Any, Any]]:
    """
    Converts a DataFrame to records, replacing missing values with None.

    Column labels must be unique. This is useful for inserting into databases
    that expect `None` for nulls.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to convert.

    Returns
    -------
    list of dict
        A list of records (dicts), where each dict is a row in the DataFrame.

    Examples
    --------
    >>> import pandas as pd
    >>> from abraxos import to_records
    >>> df = pd.DataFrame({'a': [1, None], 'b': ['x', 'y']})
    >>> to_records(df)
    [{'a': 1.0, 'b': 'x'}, {'a': None, 'b': 'y'}]
    """
    _require_unique_columns(df)
    if len(df.columns) == 0:
        return [{} for _ in df.index]
    return df.astype(object).where(df.notna(), None).to_dict('records')


def _require_unique_columns(df: pd.DataFrame) -> None:
    if not df.columns.is_unique:
        raise ValueError('DataFrame column labels must be unique')
