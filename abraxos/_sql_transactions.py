"""Transaction handling for SQLAlchemy loads."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.engine import Connection

from .exceptions import LoadError

# These backends have transactional DDL and are exercised by the integration tests.
TRANSACTIONAL_BACKENDS = frozenset({'sqlite', 'postgresql'})


def _postgres_status(driver: Any) -> int | None:
    status = getattr(getattr(driver, 'info', None), 'transaction_status', None)
    if status is None:
        get_status = getattr(driver, 'get_transaction_status', None)
        status = get_status() if callable(get_status) else None
    return int(status) if status is not None else None


def _transaction_is_open(connection: Connection) -> bool:
    if connection.closed or connection.invalidated or not connection.in_transaction():
        return False
    driver = connection.connection.driver_connection
    if isinstance(driver, sqlite3.Connection):
        return driver.in_transaction
    if connection.dialect.name == 'postgresql':
        status = _postgres_status(driver)
        # libpq reports 2 for INTRANS and 3 for INERROR. A failed PostgreSQL
        # transaction can still recover by rolling back to its savepoint.
        return status in (None, 2, 3)
    return True


def _reject_autocommit(connection: Connection) -> None:
    driver = connection.connection.driver_connection
    get_autocommit = getattr(driver, 'get_autocommit', None)
    if (
        connection.get_execution_options().get('isolation_level') == 'AUTOCOMMIT'
        or getattr(driver, 'autocommit', None) is True
        or (callable(get_autocommit) and get_autocommit())
    ):
        raise LoadError('SQL loads require driver autocommit to be disabled')


def _start_driver_transaction(connection: Connection) -> None:
    driver = connection.connection.driver_connection
    if isinstance(driver, sqlite3.Connection) and not driver.in_transaction:
        if driver.isolation_level is None:
            raise LoadError('SQL loads require SQLite autocommit to be disabled')
        # Legacy sqlite3 does not start a transaction for SAVEPOINT or DDL.
        connection.exec_driver_sql('BEGIN').close()
    elif connection.dialect.name == 'postgresql' and _postgres_status(driver) == 0:
        # SQLAlchemy's begin() is logical until the driver sends a statement.
        connection.exec_driver_sql('SELECT 1').close()
    if not _transaction_is_open(connection):
        raise LoadError('The database transaction could not be started')


@contextmanager
def savepoint(connection: Connection) -> Iterator[None]:
    """Unwind a failed attempt only while its savepoint can be rolled back."""
    try:
        if not _transaction_is_open(connection):
            raise LoadError('The database transaction is no longer active')
        transaction = connection.begin_nested()
    except Exception as error:
        raise LoadError('Could not start a SQL savepoint') from error

    try:
        yield
    except BaseException as error:
        try:
            if not transaction.is_active or not _transaction_is_open(connection):
                raise LoadError('The savepoint or outer transaction is no longer active')
            transaction.rollback()
            if not _transaction_is_open(connection):
                raise LoadError('The outer transaction did not survive savepoint rollback')
        except Exception as rollback_error:
            if isinstance(error, Exception) and not isinstance(error, LoadError):
                failure = LoadError('SQL recovery stopped because rollback could not be confirmed')
                failure.add_note(str(rollback_error))
                raise failure from error
            error.add_note(f'SQL savepoint cleanup failed: {rollback_error}')
        raise
    else:
        try:
            if not transaction.is_active or not _transaction_is_open(connection):
                raise LoadError('The savepoint or outer transaction is no longer active')
            transaction.commit()
            if not _transaction_is_open(connection):
                raise LoadError('The outer transaction did not survive savepoint release')
        except Exception as error:
            raise LoadError('Could not release the SQL savepoint') from error


@contextmanager
def load_transaction(connection: Connection, *, keep_open: bool = False) -> Iterator[None]:
    """Commit a complete load or isolate it in the caller's transaction."""
    caller_transaction = connection.in_transaction()
    try:
        _reject_autocommit(connection)
    except LoadError:
        raise
    except Exception as error:
        raise LoadError('Could not inspect the SQL connection') from error

    try:
        if not caller_transaction:
            connection.begin()
        _start_driver_transaction(connection)
        if caller_transaction or keep_open:
            with savepoint(connection):
                yield
        else:
            yield
            try:
                connection.commit()
            except Exception as error:
                # A failed commit can deactivate SQLAlchemy's transaction handle
                # while the driver still holds a transaction (e.g. deferred FKs
                # on SQLite). Roll back the driver before clearing the handle.
                try:
                    if not connection.invalidated:
                        connection.connection.rollback()
                except Exception as rollback_error:
                    error.add_note(f'Driver rollback after commit failure failed: {rollback_error}')
                    connection.invalidate()
                raise LoadError('SQL load failed while committing its transaction') from error
    except BaseException as error:
        try:
            # Clear SQLAlchemy's transaction handle if the server already rolled
            # it back. A live caller-owned transaction stays with the caller.
            if not caller_transaction or not _transaction_is_open(connection):
                connection.rollback()
        except Exception as rollback_error:
            error.add_note(f'SQL transaction cleanup failed: {rollback_error}')
        if isinstance(error, LoadError) or not isinstance(error, Exception):
            raise
        raise LoadError('SQL load could not complete its transaction') from error
