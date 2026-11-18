"""Prepare DataFrame writes and execute batches using SQLAlchemy."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from contextlib import nullcontext
from typing import Any, Literal

import pandas as pd
from sqlalchemy import Table, create_engine, inspect
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.types import NullType

from ._batch import apply_in_batches
from ._sql_transactions import TRANSACTIONAL_BACKENDS, load_transaction, savepoint
from .exceptions import LoadError


def _prepare_table_insert(
    df: pd.DataFrame,
    name: str,
    table: Table | None,
    index: bool,
    options: dict[str, Any],
) -> list[Hashable]:
    if table is None:
        return []
    if not isinstance(table, Table):
        raise TypeError('table must be a SQLAlchemy Table')
    if table.name != name or options.get('schema', table.schema) != table.schema:
        raise ValueError('name and schema must match the SQLAlchemy Table')
    options['schema'] = table.schema

    overrides = options.get('dtype')
    if overrides is not None and not pd.api.types.is_dict_like(overrides):
        return []

    index_names: list[Hashable] = []
    if index:
        label = options.get('index_label')
        if label is not None:
            index_names = label if isinstance(label, list) else [label]
        elif df.index.nlevels == 1 and df.index.name is None and 'index' not in df.columns:
            index_names = ['index']
        else:
            index_names = [
                name if name is not None else f'level_{position}'
                for position, name in enumerate(df.index.names)
            ]
        if len(index_names) != df.index.nlevels:
            index_names = []  # pandas validates the index_label length during insertion

    column_types = {
        column.name: column.type
        for column in table.columns
        if not isinstance(column.type, NullType)
    }
    dtypes = {
        label: column_types[str(label)]
        for label in [*df.columns, *index_names]
        if str(label) in column_types
    }
    if overrides is not None:
        for original, label in zip(df.index.names, index_names):
            if original in overrides:
                dtypes[label] = overrides[original]
        dtypes.update(overrides)
    options['dtype'] = dtypes
    return index_names if index_names != list(df.index.names) else []


def execute_batches(
    df: pd.DataFrame,
    db: Connection,
    operation: Callable[[pd.DataFrame], pd.DataFrame],
    chunks: int,
    *,
    is_row_error: Callable[[Exception], bool],
    split_on_error: bool = True,
    keep_open: bool = False,
) -> tuple[list[Exception], pd.DataFrame, pd.DataFrame]:
    """Run each attempt inside a savepoint within a single load transaction."""

    def attempt(batch: pd.DataFrame) -> pd.DataFrame:
        with savepoint(db):
            return operation(batch)

    def recoverable(error: Exception) -> bool:
        return supports_recovery and is_row_error(error)

    with load_transaction(db, keep_open=keep_open):
        supports_recovery = db.dialect.name in TRANSACTIONAL_BACKENDS
        return apply_in_batches(
            df, attempt, chunks, split_on_error=split_on_error, recoverable=recoverable
        )


def load_frame(
    df: pd.DataFrame,
    name: str,
    con: Connection | Engine | str,
    *,
    if_exists: Literal['fail', 'replace', 'append'],
    index: bool,
    chunks: int,
    table: Table | None,
    options: dict[str, Any],
    is_row_error: Callable[[Exception], bool],
) -> tuple[list[Exception], pd.DataFrame, pd.DataFrame]:
    """Prepare the target and write through a SQLAlchemy connection."""
    index_names = _prepare_table_insert(df, name, table, index, options)

    engine: Engine | None = None
    try:
        if isinstance(con, str):
            engine = create_engine(con)
        source = engine if engine is not None else con
        with source.connect() if isinstance(source, Engine) else nullcontext(source) as db:
            if not isinstance(db, Connection):
                raise TypeError('con must be a SQLAlchemy connection, engine or URL, or sqlite3')
            if if_exists == 'replace' and db.dialect.name not in TRANSACTIONAL_BACKENDS:
                raise LoadError(
                    'Replacing tables requires transactional DDL on SQLite or PostgreSQL'
                )

            def insert(batch: pd.DataFrame) -> pd.DataFrame:
                mode = if_exists
                if table is not None:
                    if mode == 'replace':
                        table.drop(db, checkfirst=True)
                    if mode == 'fail' and inspect(db).has_table(name, schema=table.schema):
                        raise ValueError(f'Table {name!r} already exists')
                    table.create(db, checkfirst=mode == 'append')
                    mode = 'append'
                frame = batch
                if index_names:
                    # pandas looks up dtype using the source index level names.
                    frame = batch.copy(deep=False)
                    frame.index = batch.index.set_names(index_names)
                frame.to_sql(name, db, if_exists=mode, index=index, **options)
                return batch

            return execute_batches(
                df,
                db,
                insert,
                chunks,
                is_row_error=is_row_error,
                split_on_error=if_exists == 'append',
            )
    except LoadError:
        raise
    except Exception as error:
        raise LoadError('SQL load could not be started or completed') from error
    finally:
        if engine is not None:
            engine.dispose()
