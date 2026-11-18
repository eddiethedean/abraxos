"""DataFrame transformation with error isolation."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any, NamedTuple

import pandas as pd

from ._batch import apply_in_batches
from .exceptions import TransformError

__all__ = ['TransformResult', 'transform']


class TransformResult(NamedTuple):
    """
    Result of applying a transformation to a DataFrame.

    Attributes
    ----------
    errors : list of Exception
        Exceptions raised during transformation.
    errored_df : pandas.DataFrame
        Rows that failed to transform.
    success_df : pandas.DataFrame
        Successfully transformed rows.
    """

    errors: list[Exception]
    errored_df: pd.DataFrame
    success_df: pd.DataFrame


def transform(
    df: pd.DataFrame,
    transformer: Callable[[pd.DataFrame], pd.DataFrame],
    chunks: int = 2,
    *,
    split_on_error: bool = True,
) -> TransformResult:
    """
    Applies a transformation function to a DataFrame with error isolation.

    If the transformation raises an exception on a chunk, the DataFrame
    is split into smaller chunks recursively to isolate errors. Ultimately,
    rows that fail even as single-row DataFrames are collected separately.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame to transform.
    transformer : Callable[[pd.DataFrame], pd.DataFrame]
        A function that receives a copy of a batch and returns a DataFrame.
    chunks : int, optional
        Maximum number of parts per failed batch, at least 2 (default is 2).
    split_on_error : bool, optional
        Retry failed batches in smaller parts (default is True). Use False
        for whole-frame operations such as ranking and normalization.

    Notes
    -----
    With splitting enabled, the callback should produce equivalent row values
    on smaller batches. Object cells are copied before each attempt. External
    side effects and mutations of objects captured by the callback are the
    caller's responsibility.

    Returns
    -------
    TransformResult
        A named tuple with:
        - errors: A list of exceptions that occurred during transformation.
        - errored_df: A DataFrame of rows that could not be transformed.
        - success_df: A DataFrame of successfully transformed rows.

    Examples
    --------
    >>> import pandas as pd
    >>> from abraxos import transform
    >>> def double_values(batch):
    ...     return batch.assign(value=batch['value'] * 2)
    >>> df = pd.DataFrame({'value': [1, 2, 3]})
    >>> result = transform(df, double_values)
    >>> result.success_df['value'].tolist()
    [2, 4, 6]
    >>> result.errored_df.empty
    True
    """

    return TransformResult(
        *apply_in_batches(
            df, transformer, chunks, split_on_error=split_on_error, prepare=_copy_batch
        )
    )


def _copy_batch(batch: pd.DataFrame) -> pd.DataFrame:
    copied = batch.copy()
    memo: dict[int, Any] = {}
    for position, dtype in enumerate(batch.dtypes):
        if pd.api.types.is_object_dtype(dtype):
            try:
                values = [deepcopy(value, memo) for value in batch.iloc[:, position]]
            except Exception as error:
                label = batch.columns[position]
                raise TransformError(f'Cannot copy object values in column {label!r}') from error
            copied.isetitem(position, pd.Series(values, dtype=object).to_numpy())
    return copied
