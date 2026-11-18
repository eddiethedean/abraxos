"""Shared row-level recovery for DataFrame operations."""

from __future__ import annotations

from collections.abc import Callable
from operator import index

import pandas as pd

from .utils import _partition_bounds, clear


def _chunk_count(chunks: int) -> int:
    count = index(chunks)
    if count < 2:
        raise ValueError('chunks must be at least 2')
    return count


def apply_in_batches(
    df: pd.DataFrame,
    operation: Callable[[pd.DataFrame], pd.DataFrame],
    chunks: int,
    *,
    split_on_error: bool = True,
    recoverable: Callable[[Exception], bool] | None = None,
    prepare: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> tuple[list[Exception], pd.DataFrame, pd.DataFrame]:
    count = _chunk_count(chunks)
    errors: list[Exception] = []
    failed: list[pd.DataFrame] = []
    succeeded: list[tuple[int, int, pd.DataFrame]] = []

    def visit(start: int, stop: int) -> None:
        batch = df if start == 0 and stop == len(df) else df.iloc[start:stop]
        prepared = prepare(batch) if prepare is not None else batch
        try:
            result = operation(prepared)
        except Exception as error:
            if recoverable is not None and not recoverable(error):
                raise
            size = stop - start
            if split_on_error and size > 1:
                for left, right in _partition_bounds(size, min(count, size)):
                    visit(start + left, start + right)
            else:
                errors.append(error)
                failed.append(batch)
        else:
            if not isinstance(result, pd.DataFrame):
                raise TypeError(
                    f'Batch at input positions {start}:{stop} must return a DataFrame, '
                    f'got {type(result).__name__}'
                )
            succeeded.append((start, stop, result))

    visit(0, len(df))
    try:
        success_df = _combine([frame for _, _, frame in succeeded], df)
    except Exception as error:
        ranges = ', '.join(f'{start}:{stop}' for start, stop, _ in succeeded[:8])
        raise ValueError(
            f'Cannot combine {len(succeeded)} successful batches with input positions {ranges}'
        ) from error
    return errors, _combine(failed, df), success_df


def _combine(frames: list[pd.DataFrame], original: pd.DataFrame) -> pd.DataFrame:
    if not frames:
        return clear(original)
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames)
