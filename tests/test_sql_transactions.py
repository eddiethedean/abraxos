"""Regression tests for database state and the SQL load result."""

import sqlite3
from contextlib import closing
from os import environ
from typing import get_type_hints
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import (
    JSON,
    URL,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    inspect,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.types import TypeDecorator

from abraxos import LoadError, to_sql, use_sql


@pytest.fixture(params=['sqlite', pytest.param('postgresql', marks=pytest.mark.postgres)])
def transaction_engine(request):
    if request.param == 'sqlite':
        yield request.getfixturevalue('sqlite_engine')
        return

    url = environ.get('ABRAXOS_TEST_POSTGRES')
    if not url:
        pytest.skip('set ABRAXOS_TEST_POSTGRES to a PostgreSQL test database URL')
    schema = f'abraxos_test_{uuid4().hex}'
    bootstrap = create_engine(url)
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        with bootstrap.begin() as connection:
            connection.execute(CreateSchema(schema))
        yield engine
    finally:
        engine.dispose()
        try:
            with bootstrap.begin() as connection:
                connection.execute(DropSchema(schema, if_exists=True, cascade=True))
        finally:
            bootstrap.dispose()


@pytest.mark.parametrize('idle_connection', [False, True], ids=['engine', 'idle-connection'])
def test_append_commits_once_after_failed_attempt_rolls_back(transaction_engine, idle_connection):
    table = Table('items', MetaData(), Column('id', Integer), CheckConstraint('id > 0'))
    table.create(transaction_engine)
    commits = []
    event.listen(transaction_engine, 'commit', commits.append)
    source = pd.DataFrame({'id': [1, -1, 2]})

    if idle_connection:
        with transaction_engine.connect() as db:
            result = to_sql(source, table.name, db, method=None, chunksize=1)
            assert not db.in_transaction()
            assert not db.closed
    else:
        result = to_sql(source, table.name, transaction_engine, method=None, chunksize=1)

    assert len(commits) == 1
    assert len(result.errors) == 1
    pd.testing.assert_frame_equal(result.success_df, source.iloc[[0, 2]])
    pd.testing.assert_frame_equal(result.errored_df, source.iloc[[1]])
    with transaction_engine.connect() as db:
        assert db.execute(table.select().order_by(table.c.id)).scalars().all() == [1, 2]


def test_terminal_failure_undoes_earlier_successful_attempts(transaction_engine):
    table = Table('items', MetaData(), Column('id', Integer), CheckConstraint('id > 0'))
    table.create(transaction_engine)
    calls = []

    def write_or_fail(sql_table, db, keys, rows):
        records = [dict(zip(keys, row, strict=True)) for row in rows]
        ids = [record['id'] for record in records]
        calls.append(ids)
        if ids == [2]:
            raise ConnectionError('unavailable after another batch succeeded')
        return db.execute(sql_table.table.insert(), records).rowcount

    with transaction_engine.connect() as db:
        transaction = db.begin()
        db.execute(table.insert().values(id=99))
        with pytest.raises(LoadError) as raised:
            to_sql(pd.DataFrame({'id': [1, -1, 2]}), 'items', db, method=write_or_fail)
        assert isinstance(raised.value.__cause__, ConnectionError)
        assert calls == [[1, -1, 2], [1, -1], [1], [-1], [2]]
        assert transaction.is_active
        assert db.execute(table.select()).scalars().all() == [99]
        transaction.commit()
    with transaction_engine.connect() as db:
        assert db.execute(table.select()).scalars().all() == [99]


@pytest.mark.parametrize(
    'caller_transaction', [False, True], ids=['idle-connection', 'caller-transaction']
)
def test_explicit_insert_keeps_successful_rows_in_the_caller_transaction(
    transaction_engine, caller_transaction
):
    table = Table('items', MetaData(), Column('id', Integer, primary_key=True))
    table.create(transaction_engine)
    source = pd.DataFrame({'id': [1, 1, 2]})

    with transaction_engine.connect() as db:
        if caller_transaction:
            db.execute(table.insert().values(id=99))
        result = use_sql(source, db, table.insert())
        assert result.success_df.index.tolist() == [0, 2]
        assert result.errored_df.index.tolist() == [1]
        assert db.in_transaction()
        expected = [1, 2, 99] if caller_transaction else [1, 2]
        assert db.execute(table.select().order_by(table.c.id)).scalars().all() == expected
        db.rollback()
        assert db.execute(table.select()).all() == []


@pytest.mark.parametrize('explicit_engine_option', [False, True])
def test_autocommit_is_rejected_without_schema_or_data_changes(
    transaction_engine, explicit_engine_option
):
    df = pd.DataFrame({'id': [1, -1, 2]})
    table = Table('items', MetaData(), Column('id', Integer), CheckConstraint('id > 0'))
    if explicit_engine_option:
        with transaction_engine.connect() as db:
            db.execution_options(isolation_level='AUTOCOMMIT')
            with pytest.raises(LoadError, match='autocommit'):
                to_sql(df, table.name, db, table=table, method=None, chunksize=1)
            with pytest.raises(LoadError, match='autocommit'):
                use_sql(df, db, table.insert())
    else:
        # Set autocommit directly to exercise the driver check, independently
        # of the SQLAlchemy execution options dictionary.
        with transaction_engine.connect() as db:
            driver = db.connection.driver_connection
            if isinstance(driver, sqlite3.Connection):
                driver.isolation_level = None
            else:
                driver.autocommit = True
            with pytest.raises(LoadError, match='autocommit'):
                to_sql(df, table.name, db, table=table, method=None, chunksize=1)
    assert not inspect(transaction_engine).has_table(table.name)


@pytest.mark.parametrize('composite', [False, True])
def test_schema_creation_and_failed_replace_preserve_primary_key(transaction_engine, composite):
    schema = inspect(transaction_engine).default_schema_name
    table = Table(
        'items',
        MetaData(),
        Column('id', Integer, primary_key=True),
        Column('group_id', Integer, primary_key=composite),
        schema=schema,
    )
    source = pd.DataFrame({'id': [99], 'group_id': [4]})
    result = to_sql(source, name=table.name, con=transaction_engine, table=table)
    pd.testing.assert_frame_equal(result.success_df, source)
    key = ['id', 'group_id'] if composite else ['id']
    assert inspect(transaction_engine).get_pk_constraint(table.name)['constrained_columns'] == key

    with pytest.raises(LoadError) as raised:
        to_sql(source, table.name, transaction_engine, table=table, if_exists='fail')
    assert isinstance(raised.value.__cause__, ValueError)

    duplicate = pd.DataFrame({'id': [1, 1], 'group_id': [6, 6]})
    result = to_sql(duplicate, table.name, transaction_engine, table=table, if_exists='replace')
    assert len(result.errors) == 1
    assert result.success_df.empty
    pd.testing.assert_frame_equal(result.errored_df, duplicate)
    with transaction_engine.connect() as db:
        assert db.execute(table.select()).all() == [(99, 4)]
        assert inspect(db).get_pk_constraint(table.name)['constrained_columns'] == key


def test_schema_and_name_must_agree_before_creating_a_table(sqlite_engine):
    table = Table('items', MetaData(), Column('id', Integer, primary_key=True))
    df = pd.DataFrame({'id': [1]})
    with pytest.raises(ValueError, match='name and schema'):
        to_sql(df, 'different_name', sqlite_engine, table=table)
    with pytest.raises(ValueError, match='name and schema'):
        to_sql(df, table.name, sqlite_engine, table=table, schema='other_schema')
    assert inspect(sqlite_engine).get_table_names() == []


@pytest.mark.parametrize('override_label', [False, True])
def test_table_types_bind_values_and_renamed_index(transaction_engine, override_label):
    class PrefixedText(TypeDecorator):
        impl = String
        cache_ok = True

        def process_bind_param(self, value, dialect):
            return f'bound-{value}'

    table = Table(
        'items',
        MetaData(),
        Column('item_id', PrefixedText(), primary_key=True),
        Column('payload', JSON),
        Column('label', String),
    )
    source = pd.DataFrame(
        {'payload': [{'status': 'new'}], 'label': ['first']},
        index=pd.Index(['one'], name='source_id'),
    )
    dtypes = {'label': PrefixedText()} if override_label else None
    result = to_sql(
        source,
        table.name,
        transaction_engine,
        table=table,
        index=True,
        index_label='item_id',
        dtype=dtypes,
    )

    assert result.errors == []
    assert source.index.name == 'source_id'
    pd.testing.assert_frame_equal(result.success_df, source)
    expected_label = 'bound-first' if override_label else 'first'
    with transaction_engine.connect() as db:
        assert db.execute(table.select()).all() == [
            ('bound-one', {'status': 'new'}, expected_label)
        ]


def test_sqlalchemy_url_owns_the_connection_and_commits(tmp_path):
    url = URL.create('sqlite', database=str(tmp_path / 'load.db')).render_as_string()
    result = to_sql(pd.DataFrame({'id': [1]}), 'items', url)
    assert result.errors == []
    with closing(sqlite3.connect(tmp_path / 'load.db')) as db:
        assert db.execute('SELECT id FROM items').fetchall() == [(1,)]


@pytest.mark.skipif(not hasattr(sqlite3, 'LEGACY_TRANSACTION_CONTROL'), reason='Python 3.12+')
def test_modern_sqlite_transaction_modes(tmp_path):
    url = URL.create('sqlite', database=str(tmp_path / 'modern.db'))
    transactional = create_engine(url, connect_args={'autocommit': False})
    autocommit = create_engine(url, connect_args={'autocommit': True})
    try:
        table = Table('items', MetaData(), Column('id', Integer, primary_key=True))
        result = to_sql(
            pd.DataFrame({'id': [1, 1, 2]}), table.name, transactional, table=table, method=None
        )
        assert len(result.errors) == 1
        assert result.success_df['id'].tolist() == [1, 2]
        with pytest.raises(LoadError, match='autocommit'):
            to_sql(pd.DataFrame({'id': [3]}), table.name, autocommit)
        with transactional.connect() as db:
            assert db.execute(table.select().order_by(table.c.id)).scalars().all() == [1, 2]
    finally:
        autocommit.dispose()
        transactional.dispose()


def test_disconnection_stops_recovery_and_preserves_its_cause(sqlite_engine):
    failure = ConnectionError('connection lost')
    calls = []

    def disconnect(sql_table, db, keys, rows):
        calls.append(list(rows))
        db.invalidate()
        raise failure

    with pytest.raises(LoadError, match='rollback could not be confirmed') as raised:
        to_sql(pd.DataFrame({'id': [1, 2]}), 'items', sqlite_engine, method=disconnect)
    assert raised.value.__cause__ is failure
    assert calls == [[(1,), (2,)]]


def test_deferred_constraint_error_rolls_back_a_failed_commit(transaction_engine):
    metadata = MetaData()
    Table('parents', metadata, Column('id', Integer, primary_key=True))
    children = Table(
        'children',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('parent_id', ForeignKey('parents.id', deferrable=True, initially='DEFERRED')),
    )
    with transaction_engine.connect() as db:
        if db.dialect.name == 'sqlite':
            db.exec_driver_sql('PRAGMA foreign_keys=ON')
            db.commit()
        metadata.create_all(db)
        db.commit()
        with pytest.raises(LoadError, match='committing') as raised:
            to_sql(pd.DataFrame({'id': [1], 'parent_id': [999]}), children.name, db)
        assert isinstance(raised.value.__cause__, IntegrityError)
        assert not db.in_transaction()
        if db.dialect.name == 'sqlite':
            assert not db.connection.driver_connection.in_transaction
        assert db.execute(children.select()).all() == []


def test_sqlite_conflict_rollback_stops_the_load_and_preserves_the_original_error(sqlite_engine):
    with sqlite_engine.begin() as db:
        db.exec_driver_sql('CREATE TABLE items (id INTEGER UNIQUE ON CONFLICT ROLLBACK)')
        db.exec_driver_sql('CREATE TABLE earlier (id INTEGER)')
        db.exec_driver_sql('INSERT INTO items VALUES (99)')
    table = Table('items', MetaData(), autoload_with=sqlite_engine)
    inserts = []

    @event.listens_for(sqlite_engine, 'before_cursor_execute')
    def record_attempts(db, cursor, statement, parameters, context, many):
        if statement.startswith('INSERT INTO items'):
            inserts.append(parameters)

    with sqlite_engine.connect() as db:
        db.exec_driver_sql('INSERT INTO earlier VALUES (33)')
        with pytest.raises(LoadError, match='rollback could not be confirmed') as raised:
            use_sql(pd.DataFrame({'id': [1, 99, 2]}), db, table.insert())
        assert isinstance(raised.value.__cause__, IntegrityError)
        assert not db.in_transaction()
        assert db.execute(table.select()).scalars().all() == [99]
        assert db.exec_driver_sql('SELECT * FROM earlier').all() == []
    assert len(inserts) == 1


def test_raw_sqlite_rejects_replace_and_preserves_caller_transaction():
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('CREATE TABLE items (id INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO items VALUES (99)')
        db.commit()
        df = pd.DataFrame({'id': [1, 1]})
        with pytest.raises(LoadError, match='requires SQLAlchemy'):
            to_sql(df, 'items', db, if_exists='replace', dtype={'id': 'INTEGER PRIMARY KEY'})
        assert db.execute('SELECT id FROM items').fetchall() == [(99,)]

        db.execute('INSERT INTO items VALUES (33)')
        with pytest.raises(LoadError, match='active transaction'):
            to_sql(df, 'items', db)
        assert db.in_transaction
        db.rollback()
        assert db.execute('SELECT id FROM items').fetchall() == [(99,)]


def test_raw_sqlite_single_attempt_rolls_back_all_rows_but_can_create_the_table():
    df = pd.DataFrame({'id': [1, 1]})
    with closing(sqlite3.connect(':memory:')) as db:
        result = to_sql(
            df, 'items', db, method=None, chunksize=1, dtype={'id': 'INTEGER PRIMARY KEY'}
        )
        assert len(result.errors) == 1
        pd.testing.assert_frame_equal(result.errored_df, df)
        assert result.success_df.empty
        assert db.execute('SELECT * FROM items').fetchall() == []
        assert db.execute('PRAGMA table_info(items)').fetchone()[5] == 1
    with closing(sqlite3.connect(':memory:', isolation_level=None)) as db:
        with pytest.raises(LoadError, match='autocommit'):
            to_sql(df, 'items', db)
        assert db.execute('SELECT name FROM sqlite_master').fetchall() == []


def test_batch_level_outage_is_attempted_once_even_when_a_custom_adapter_opts_in():
    failure = ConnectionError('connection unavailable')

    class Connection:
        attempts = 0

        def execute(self, query, records):
            self.attempts += 1
            raise failure

    db = Connection()
    df = pd.DataFrame({'id': range(1024)})
    with pytest.raises(LoadError) as raised:
        use_sql(df, db, object(), retry_if=lambda error: isinstance(error, ValueError))
    assert raised.value.__cause__ is failure
    assert db.attempts == 1


def test_missing_table_is_attempted_once_in_sqlalchemy(sqlite_engine):
    table = Table('missing', MetaData(), Column('id', Integer))
    attempts = []

    @event.listens_for(sqlite_engine, 'before_cursor_execute')
    def record_attempts(db, cursor, statement, parameters, context, many):
        if statement.startswith('INSERT INTO missing'):
            attempts.append(parameters)

    with sqlite_engine.connect() as db:
        with pytest.raises(LoadError) as raised:
            use_sql(pd.DataFrame({'id': range(1024)}), db, table.insert())
        assert not db.in_transaction()
    assert isinstance(raised.value.__cause__, OperationalError)
    assert len(attempts) == 1


def test_duplicate_labels_are_rejected_before_adapter_execution():
    class Adapter:
        def execute(self, query, records):
            pytest.fail('duplicate labels must be rejected before execution')

    df = pd.DataFrame([[1, 2]], columns=['id', 'id'])
    with pytest.raises(ValueError, match='labels must be unique'):
        use_sql(df, Adapter(), object())


def test_invalid_custom_retry_predicate_is_rejected_before_execution():
    class Adapter:
        def execute(self, query, records):
            pytest.fail('invalid retry policy must be rejected before execution')

    with pytest.raises(TypeError, match='retry_if must be callable'):
        use_sql(pd.DataFrame({'id': [1]}), Adapter(), object(), retry_if=True)


def test_to_sql_runtime_annotations_resolve():
    annotations = get_type_hints(to_sql)
    assert 'con' in annotations
    assert 'table' in annotations
