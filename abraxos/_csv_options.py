"""Partition CSV reader options from pandas conversion options."""

from __future__ import annotations

import csv
from _csv import Dialect
from collections.abc import Callable
from operator import index
from typing import Any, NamedTuple

_SOURCE_OPTIONS = ('compression', 'storage_options', 'memory_map', 'encoding', 'encoding_errors')


class ReaderOptions(NamedTuple):
    dialect: Dialect
    skip_rows: Callable[[int], bool]
    skip_blank_lines: bool
    comment: str | None
    header: int | None
    nrows: int | None
    skip_footer: int
    source_options: dict[str, Any]
    pandas_options: dict[str, Any]


def _dialect(options: dict[str, Any]) -> Dialect:
    configured = options.pop('dialect', None)
    base = csv.get_dialect(configured) if isinstance(configured, str) else configured
    overrides: dict[str, Any] = {}
    if 'sep' in options or 'delimiter' in options:
        if 'sep' in options and 'delimiter' in options:
            raise ValueError('Specify sep or delimiter, not both')
        separator = options.pop('sep') if 'sep' in options else options.pop('delimiter')
        if not isinstance(separator, str) or len(separator) != 1:
            raise ValueError('CSV recovery requires an explicit one-character separator')
        overrides['delimiter'] = separator
    for key in ('quotechar', 'quoting', 'doublequote', 'escapechar', 'skipinitialspace'):
        if key in options:
            overrides[key] = options.pop(key)
    if base is not None:
        for key, value in overrides.items():
            if getattr(base, key) != value:
                raise ValueError(f'{key} conflicts with the specified CSV dialect')
    parsed = csv.reader((), base if base is not None else 'excel', **overrides).dialect
    if parsed.quoting not in (csv.QUOTE_MINIMAL, csv.QUOTE_ALL, csv.QUOTE_NONE):
        raise ValueError('CSV recovery requires a quoting mode that preserves text fields')
    return parsed


def _skip_rows(skiprows: Any) -> Callable[[int], bool]:
    if skiprows is None:
        return lambda _line: False
    if callable(skiprows):
        return lambda line: bool(skiprows(line))
    if hasattr(skiprows, '__index__'):
        count = index(skiprows)
        if count < 0:
            raise ValueError('skiprows must be non-negative')
        return lambda line: line < count
    selected = {index(line) for line in skiprows}
    return selected.__contains__


def parse_reader_options(kwargs: dict[str, Any]) -> ReaderOptions:
    """Validate reader controls and separate them from options forwarded to pandas."""
    options = kwargs.copy()
    if options.pop('iterator', False):
        raise ValueError('Use read_csv_chunks() to read in chunks')
    if options.pop('engine', None) not in (None, 'python') or 'on_bad_lines' in options:
        raise ValueError('CSV recovery controls engine and on_bad_lines')
    if options.pop('lineterminator', None) is not None:
        raise ValueError('CSV recovery uses standard line endings')

    dialect = _dialect(options)
    skip = _skip_rows(options.pop('skiprows', None))
    skip_blanks = options.pop('skip_blank_lines', True)
    comment = options.pop('comment', None)
    if comment is not None and (not isinstance(comment, str) or len(comment) != 1):
        raise ValueError('comment must be one character')
    if comment is not None and comment in (
        dialect.delimiter,
        dialect.quotechar,
        dialect.escapechar,
    ):
        raise ValueError('comment conflicts with the specified CSV dialect')
    header_setting = options.pop('header', 'infer')
    if isinstance(header_setting, str) and header_setting == 'infer':
        header_setting = 0 if options.get('names') is None else None
    header = index(header_setting) if hasattr(header_setting, '__index__') else None
    if isinstance(header_setting, bool) or (
        header_setting is not None and (header is None or header < 0)
    ):
        raise ValueError('CSV recovery supports one header row or header=None')
    limit_value = options.pop('nrows', None)
    limit = index(limit_value) if limit_value is not None else None
    footer = index(options.pop('skipfooter', 0))
    if footer < 0 or (limit is not None and limit < 0):
        raise ValueError('nrows and skipfooter must be non-negative')
    if limit is not None and footer:
        raise ValueError('skipfooter cannot be combined with nrows')

    source_options = {name: options.pop(name) for name in _SOURCE_OPTIONS if name in options}
    return ReaderOptions(
        dialect=dialect,
        skip_rows=skip,
        skip_blank_lines=skip_blanks,
        comment=comment,
        header=header,
        nrows=limit,
        skip_footer=footer,
        source_options=source_options,
        pandas_options=options,
    )
