Write DataFrames to SQL
=======================

Create a table with a primary key
---------------------------------

Pass a SQLAlchemy ``Table`` to :func:`~abraxos.load.to_sql` to create a
missing table with a primary key and other constraints. The table definition
and load options must use the same name and schema. For a composite primary
key, mark each participating ``Column`` with ``primary_key=True``.

.. testcode:: sql-transactions

   import pandas as pd
   from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

   from abraxos import to_sql, use_sql

   people = Table(
       'people',
       MetaData(),
       Column('id', Integer, primary_key=True),
       Column('name', String(100), nullable=False),
   )
   engine = create_engine('sqlite://')
   source = pd.DataFrame({'id': [1, 1, 2], 'name': ['Ada', 'Duplicate', 'Grace']})
   result = to_sql(source, people.name, engine, table=people)
   assert result.success_df['name'].tolist() == ['Ada', 'Grace']
   assert result.errored_df['name'].tolist() == ['Duplicate']

On SQLite and PostgreSQL, Abraxos rolls back a recoverable SQLAlchemy append
failure to a savepoint before splitting the batch. If the connection fails,
the transaction is lost, or an operation cannot safely continue, it raises
:exc:`~abraxos.exceptions.LoadError`. Disable driver autocommit before writing.

Choose what to do with an existing table
----------------------------------------

.. rst-class:: ab-sql-modes

``'append'``
   Adds rows and preserves the schema and constraints. Abraxos splits
   recoverable failures on SQLAlchemy SQLite and PostgreSQL.
``'fail'``
   Raises ``LoadError`` if the table exists. When creating a table, it writes
   the full batch in one attempt.
``'replace'``
   Recreates the table in one attempt using transactional DDL on SQLAlchemy
   SQLite or PostgreSQL. Pass ``table=`` to specify the new constraints.

If the table is missing, ``to_sql`` creates it from ``table=`` when supplied.
The table definition also supplies the column types used to bind values, such
as Python dictionaries for a SQLAlchemy ``JSON`` column. An explicit ``dtype``
overrides those types. Set ``index=True`` when the DataFrame index belongs in
the destination schema. The default insertion method is ``'multi'``. Use
``method=None`` for drivers that need standard inserts.

Control the transaction
-----------------------

The ``sql`` extra installs SQLAlchemy. For PostgreSQL, install a driver such
as ``psycopg`` separately and use a ``postgresql+psycopg://`` URL.

An engine or URL commits the completed load once. A SQLAlchemy connection
with an active transaction leaves commit and rollback to the caller.
:func:`~abraxos.load.use_sql` runs a supplied insert statement and leaves
the transaction open, including when it starts the transaction for you.
``success_df`` reports successful insert attempts. If you own the
transaction, those writes are pending until you commit.

.. testcode:: sql-transactions

   try:
       with engine.connect() as connection:
           pending = use_sql(
               pd.DataFrame({'id': [3], 'name': ['Katherine']}), connection, people.insert()
           )
           assert pending.success_df['id'].tolist() == [3]
           assert connection.in_transaction()
           connection.rollback()

       with engine.connect() as connection:
           ids = connection.execute(people.select().order_by(people.c.id)).scalars().all()
           assert ids == [1, 2]
   finally:
       engine.dispose()

For custom adapters passed to ``use_sql``, supply a ``retry_if`` predicate
to opt into row recovery. The predicate identifies row errors, and the
adapter must roll back each failed batch before raising. A custom
``to_sql`` insertion method must leave transaction control to Abraxos.

Use a raw SQLite connection
---------------------------

A dedicated ``sqlite3.Connection`` supports one standalone append or create
attempt. Use a connection with autocommit disabled and no active caller
transaction. A new empty table can remain after an insertion failure. Use
SQLAlchemy for transactional retries, replacement, or caller-owned loads.

.. testcode:: sql-raw

   import sqlite3
   from contextlib import closing

   import pandas as pd

   from abraxos import to_sql

   with closing(sqlite3.connect(':memory:')) as connection:
       result = to_sql(
           pd.DataFrame({'id': [1]}), 'people', connection, dtype={'id': 'INTEGER PRIMARY KEY'}
       )
       assert result.errors == []
       assert connection.execute('PRAGMA table_info(people)').fetchone()[5] == 1
