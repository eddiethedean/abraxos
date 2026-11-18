"""CSV reading with record-width validation before pandas conversion."""

from __future__ import annotations

import csv
from collections import deque
from collections.abc import Generator, Iterable, Iterator, Sized
from contextlib import closing
from io import StringIO
from itertools import chain, islice
from operator import index
from typing import Any, NamedTuple, overload

import pandas as pd

from ._csv_options import parse_reader_options
from ._csv_records import scan_records
from ._csv_source import CsvSource as CsvSource
from ._csv_source import open_csv_source
from .exceptions import CsvParseError as CsvParseError

__all__ = ['ReadCsvResult', 'read_csv', 'read_csv_chunks']


class ReadCsvResult(NamedTuple):
    """Accepted data and records with the wrong number of fields.

    Attributes
    ----------
    bad_lines : list of list of str
        Rejected records in source order, split into fields.
    dataframe : pandas.DataFrame
        Accepted records converted using pandas.
    """

    bad_lines: list[list[str]]
    dataframe: pd.DataFrame


def _without_footer(rows: Iterable[list[str]], count: int) -> Iterator[list[str]]:
    pending: deque[list[str]] = deque()
    for row in rows:
        pending.append(row)
        if len(pending) > count:
            yield pending.popleft()


def _frame(
    rows: list[list[str]], header_row: list[str] | None, offset: int, options: dict[str, Any]
) -> pd.DataFrame:
    with StringIO(newline='') as data:
        writer = csv.writer(data, quoting=csv.QUOTE_ALL)
        if header_row is not None:
            writer.writerow(header_row)
        writer.writerows(rows)
        data.seek(0)
        df: pd.DataFrame = pd.read_csv(
            data,
            engine='python',
            header=0 if header_row is not None else None,
            skip_blank_lines=False,
            iterator=False,
            **options,
        )
    index_col = options.get('index_col')
    default_index = (
        index_col is None
        or index_col is False
        or (isinstance(index_col, Sized) and not len(index_col))
    )
    if default_index and isinstance(df.index, pd.RangeIndex):
        df.index = pd.RangeIndex(offset, offset + len(df))
    return df


def _header(
    rows: Iterator[list[str]], options: dict[str, Any], header: int | None
) -> tuple[list[str] | None, int, Iterator[list[str]]]:
    names = options.get('names')
    header_row = next(islice(rows, header, None), None) if header is not None else None
    if names is not None:
        if isinstance(names, (str, bytes)) or len(names) == 0:
            raise ValueError('names must contain the declared CSV column labels')
        return None, len(names), rows
    if header_row is not None:
        if not header_row:
            raise pd.errors.EmptyDataError('No columns to parse from the CSV header')
        return header_row, len(header_row), rows
    if header is not None:
        raise pd.errors.EmptyDataError('No CSV header at the requested position')
    first = next(rows, None)
    if not first:
        raise pd.errors.EmptyDataError('No columns to parse from the CSV file')
    options['names'] = list(range(len(first)))
    return None, len(first), chain((first,), rows)


def _read_csv(
    path: CsvSource, chunksize: int | None, kwargs: dict[str, Any]
) -> Generator[ReadCsvResult, None, None]:
    options = parse_reader_options(kwargs)
    pandas_options = options.pandas_options
    with open_csv_source(path, **options.source_options) as (source_name, lines):
        records = scan_records(
            lines,
            source_name,
            options.dialect,
            options.skip_rows,
            options.skip_blank_lines,
            options.comment,
        )
        header_row, width, rows = _header(records, pandas_options, options.header)
        if options.skip_footer:
            rows = _without_footer(rows, options.skip_footer)

        accepted: list[list[str]] = []
        rejected: list[list[str]] = []
        remaining = options.nrows
        offset = 0
        yielded = False
        for row in rows if remaining != 0 else ():
            if len(row) != width:
                rejected.append(row)
            else:
                accepted.append(row)
                if remaining is not None:
                    remaining -= 1
            if chunksize is not None and len(accepted) + len(rejected) == chunksize:
                frame = _frame(accepted, header_row, offset, pandas_options)
                offset += len(frame)
                yield ReadCsvResult(rejected, frame)
                accepted, rejected = [], []
                yielded = True
            if remaining == 0:
                break

        if accepted or rejected or not yielded:
            yield ReadCsvResult(rejected, _frame(accepted, header_row, offset, pandas_options))


def read_csv_chunks(
    path: CsvSource, chunksize: int, **kwargs: Any
) -> Generator[ReadCsvResult, None, None]:
    """Stream accepted and rejected CSV records in input batches.

    Parameters
    ----------
    path : str, path-like, or file-like object
        Source of the CSV data.
    chunksize : int
        Maximum number of logical data records consumed per result. Rejected
        records count toward this limit.
    **kwargs
        CSV input and pandas conversion options supported by `read_csv`.

    Yields
    ------
    ReadCsvResult
        Accepted data and rejected records, including batches with only rejections.
    """
    size = index(chunksize)
    if size <= 0:
        raise ValueError('chunksize must be a positive integer')
    return _read_csv(path, size, kwargs)


def read_csv_all(path: CsvSource, **kwargs: Any) -> ReadCsvResult:
    """Read an entire CSV source and return accepted and rejected records."""
    if kwargs.pop('chunksize', None) is not None:
        raise ValueError('Use read_csv_chunks() to read in chunks')
    with closing(_read_csv(path, None, kwargs)) as results:
        return next(results)


@overload
def read_csv(path: CsvSource, *, chunksize: None = None, **kwargs: Any) -> ReadCsvResult: ...


@overload
def read_csv(
    path: CsvSource, *, chunksize: int, **kwargs: Any
) -> Generator[ReadCsvResult, None, None]: ...


@overload
def read_csv(
    path: CsvSource, *, chunksize: int | None, **kwargs: Any
) -> ReadCsvResult | Generator[ReadCsvResult, None, None]: ...


def read_csv(
    path: CsvSource, *, chunksize: int | None = None, **kwargs: Any
) -> ReadCsvResult | Generator[ReadCsvResult, None, None]:
    """Read a CSV source and capture records with an unexpected field count.

    Parameters
    ----------
    path : str, path-like, or file-like object
        Source of the CSV data.
    chunksize : int, optional
        Maximum number of logical data records per result, including rejected
        records. With None, return a single result for the whole input.
    **kwargs
        CSV options for a one-character separator, dialect, a single header,
        explicit names, row selection, and source opening. Pandas conversion
        options such as dtype, na_values, parse_dates, index_col, and usecols
        apply after width checks. A headerless input without names uses the
        first logical record to determine its width.

    Raises
    ------
    CsvParseError
        Malformed quoting or another CSV syntax error prevents safe recovery.
        The error includes the source and starting physical line of the record.
    """
    if chunksize is not None:
        return read_csv_chunks(path, chunksize, **kwargs)
    return read_csv_all(path, **kwargs)
