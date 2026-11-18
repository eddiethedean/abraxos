"""SQL loading utilities with row-level error recovery."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Protocol

import pandas as pd

from ._batch import _chunk_count, apply_in_batches
from .exceptions import LoadError
from .utils import _require_unique_columns, clear, to_records

__all__ = ['SqlInsert', 'SqlConnection', 'SqlEngine', 'ToSqlResult', 'to_sql', 'use_sql']


class SqlInsert(Protocol):
    """A SQL insert statement accepted by the supplied connection."""


class SqlConnection(Protocol):
    """A connection that executes parameterized insert statements."""

    def execute(self, insert: Any, records: list[dict[Any, Any]], /) -> object:
        """Execute an insert statement with the given records."""
        ...


class SqlEngine(Protocol):
    """An engine that provides SQL connections."""

    def connect(self) -> SqlConnection:
        """Obtain a SQL connection from the engine."""
        ...


class _SqlTable(Protocol):
    @property
    def name(self) -> str: ...


try:
    from sqlalchemy import Table
    from sqlalchemy.engine import Connection, Engine
    from sqlalchemy.exc import DataError, DBAPIError, IntegrityError
except ModuleNotFoundError as error:
    if error.name != 'sqlalchemy':
        raise
    if not TYPE_CHECKING:
        # Keep public annotations resolvable in a base install.
        Connection = SqlConnection
        Engine = SqlEngine
        Table = _SqlTable
    _HAS_SQLALCHEMY = False
else:
    from ._sqlalchemy_load import execute_batches, load_frame

    _HAS_SQLALCHEMY = True


class ToSqlResult(NamedTuple):
    """Result of inserting a DataFrame into a database.

    Attributes
    ----------
    errors : list of Exception
        Recoverable errors encountered during insertion.
    errored_df : pandas.DataFrame
        Rows whose batch was rolled back.
    success_df : pandas.DataFrame
        Rows whose insert statements succeeded. The caller must still commit
        when it owns the transaction.
    """

    errors: list[Exception]
    errored_df: pd.DataFrame
    success_df: pd.DataFrame


def _is_row_error(error: Exception) -> bool:
    """Recognize data and integrity errors, including pandas-wrapped errors."""
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (LoadError, ConnectionError)):
            return False
        if _HAS_SQLALCHEMY and isinstance(current, DBAPIError):
            if current.connection_invalidated:
                return False
            if isinstance(current, (DataError, IntegrityError)):
                return True
            current = current.orig
            continue
        if isinstance(current, (sqlite3.DataError, sqlite3.IntegrityError)):
            return True
        # PostgreSQL data exceptions and integrity constraint violations.
        state = getattr(current, 'sqlstate', None) or getattr(current, 'pgcode', None)
        if isinstance(state, str):
            return state.startswith(('22', '23'))
        current = current.__cause__
    return False


def _load_sqlite(
    df: pd.DataFrame,
    name: str,
    con: sqlite3.Connection,
    *,
    if_exists: Literal['fail', 'append'],
    index: bool,
    options: dict[str, Any],
) -> ToSqlResult:
    try:
        if con.in_transaction:
            raise LoadError('Raw sqlite3 loads require a connection without an active transaction')
        if getattr(con, 'autocommit', None) is True or con.isolation_level is None:
            raise LoadError('Raw sqlite3 loads require driver autocommit to be disabled')
        df.to_sql(name, con, if_exists=if_exists, index=index, **options)
    except LoadError:
        raise
    except Exception as error:
        if not _is_row_error(error):
            raise LoadError('Raw sqlite3 load could not complete') from error
        return ToSqlResult([error], df, clear(df))
    return ToSqlResult([], clear(df), df)


def to_sql(
    df: pd.DataFrame,
    name: str,
    con: Connection | Engine | sqlite3.Connection | str,
    *,
    if_exists: Literal['fail', 'replace', 'append'] = 'append',
    index: bool = False,
    chunks: int = 2,
    table: Table | None = None,
    **kwargs: Any,
) -> ToSqlResult:
    """Write a DataFrame to a SQL table and isolate failing rows on append.

    SQLite and PostgreSQL support row recovery with SQLAlchemy. Each failed
    attempt rolls back to a savepoint before splitting. Engine-owned loads
    commit once. An existing SQLAlchemy transaction stays open for the caller.
    A raw sqlite3 connection supports one standalone append or create attempt.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to insert.
    name : str
        Name of the target table.
    con : connection, engine, or str
        A SQLAlchemy connection, engine or URL, or a standalone sqlite3 connection.
    if_exists : {'fail', 'replace', 'append'}, optional
        SQL behavior if the table already exists (default is 'append'). Replace
        requires a SQLAlchemy connection on SQLite or PostgreSQL.
    index : bool, optional
        Whether to include the DataFrame index (default is False).
    chunks : int, optional
        Maximum number of parts per failed batch, at least 2 (default is 2).
    table : sqlalchemy.Table, optional
        Schema to use when creating the table, including primary keys and
        constraints. Its name and schema must agree with the supplied options.
        Its column types are used to bind values unless overridden by `dtype`.
    **kwargs
        Options forwarded to `pandas.DataFrame.to_sql`. The default insert
        method is 'multi'. Pass `method=None` for drivers that do not support it.
        A custom insert method must leave transaction control to Abraxos.

    Returns
    -------
    ToSqlResult
        Recoverable insert errors, failed rows, and successful rows.

    Raises
    ------
    LoadError
        The connection, statement, or transaction cannot be used safely.
    """
    chunks = _chunk_count(chunks)
    _require_unique_columns(df)
    if if_exists not in ('fail', 'replace', 'append'):
        raise ValueError('if_exists must be fail, replace, or append')
    kwargs.setdefault('method', 'multi')

    if isinstance(con, sqlite3.Connection):
        if table is not None or if_exists == 'replace':
            raise LoadError('Replacing a table or specifying its schema requires SQLAlchemy')
        return _load_sqlite(df, name, con, if_exists=if_exists, index=index, options=kwargs)

    if not _HAS_SQLALCHEMY:
        raise LoadError('Install abraxos[sql] to use a SQLAlchemy connection, engine, or URL')
    return ToSqlResult(
        *load_frame(
            df,
            name,
            con,
            if_exists=if_exists,
            index=index,
            chunks=chunks,
            table=table,
            options=kwargs,
            is_row_error=_is_row_error,
        )
    )


def _never_recover(_error: Exception) -> bool:
    return False


def insert_df(df: pd.DataFrame, connection: SqlConnection, sql_query: SqlInsert) -> ToSqlResult:
    """Execute a SQL insert statement with the rows of a DataFrame."""
    records = to_records(df)
    if records:
        connection.execute(sql_query, records)
    return ToSqlResult([], clear(df), df)


def use_sql(
    df: pd.DataFrame,
    connection: SqlConnection,
    sql_query: SqlInsert,
    chunks: int = 2,
    *,
    retry_if: Callable[[Exception], bool] | None = None,
) -> ToSqlResult:
    """Execute a supplied SQL insert statement and isolate failing rows.

    SQLAlchemy loads use savepoints, and the caller owns the final commit or
    rollback. Custom adapters attempt the batch once by default.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to insert.
    connection : SqlConnection
        A SQLAlchemy connection or an object with a compatible execute method.
    sql_query : SqlInsert
        The insert statement to execute.
    chunks : int, optional
        Maximum number of parts per failed batch, at least 2 (default is 2).
    retry_if : callable, optional
        A custom adapter can opt into retries with a predicate identifying
        row errors. The adapter must guarantee rollback of each failed batch.
        SQLAlchemy connections use Abraxos's error classification.

    Returns
    -------
    ToSqlResult
        Recoverable insert errors, failed rows, and successful rows.

    Raises
    ------
    LoadError
        A batch-level error prevents recovery or the transaction was lost.
    """
    chunks = _chunk_count(chunks)
    _require_unique_columns(df)
    if retry_if is not None and not callable(retry_if):
        raise TypeError('retry_if must be callable')
    if not len(df):
        return ToSqlResult([], clear(df), df)

    def execute(batch: pd.DataFrame) -> pd.DataFrame:
        return insert_df(batch, connection, sql_query).success_df

    if _HAS_SQLALCHEMY and isinstance(connection, Connection):
        if retry_if is not None:
            raise ValueError('retry_if is only supported for custom SQL adapters')
        return ToSqlResult(
            *execute_batches(
                df, connection, execute, chunks, is_row_error=_is_row_error, keep_open=True
            )
        )

    try:
        return ToSqlResult(
            *apply_in_batches(
                df,
                execute,
                chunks,
                recoverable=retry_if if retry_if is not None else _never_recover,
            )
        )
    except Exception as error:
        raise LoadError('Custom SQL adapter could not complete the load') from error
