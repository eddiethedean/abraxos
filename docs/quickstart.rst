Quick start
===========

Install Abraxos
---------------

Use Python 3.11 or later. The base package installs pandas and provides CSV
reading, transformations, and DataFrame utilities.

.. code-block:: bash

   uv venv --python 3.11
   uv pip install abraxos

The example below uses both optional integrations. Install them together
with the following command, or use ``python -m pip install`` with the same
package specifier in an activated environment.

.. code-block:: bash

   uv pip install 'abraxos[sql,validate]'

Run a pipeline
--------------

Each step passes its accepted data to the next step. The input includes a
CSV record with extra fields, a blank name, an invalid age, and a duplicate
person ID.

1. Read the CSV
~~~~~~~~~~~~~~~

This example uses an in-memory text stream. Replace it with a file path when
reading your own CSV. The reader collects records with the wrong field count
in ``bad_lines`` and converts the accepted records to a DataFrame.

.. testcode:: pipeline

   from io import StringIO

   from abraxos import read_csv, to_sql, transform, validate

   source = StringIO(
       'person_id,name,age\n'
       'bad,extra,fields,here\n'
       '1, Ada ,28\n'
       '2,   ,31\n'
       '3, Grace ,unknown\n'
       '1, Duplicate ,34\n'
   )
   extracted = read_csv(source)
   assert extracted.bad_lines == [['bad', 'extra', 'fields', 'here']]

2. Normalize names
~~~~~~~~~~~~~~~~~~

The callback trims names and raises when a batch contains an empty name.
Abraxos splits that failed batch until it isolates the offending row.

.. testcode:: pipeline

   def clean_names(batch):
       names = batch['name'].str.strip()
       if names.eq('').any():
           raise ValueError('A name is required')
       return batch.assign(name=names)

   cleaned = transform(extracted.dataframe, clean_names)
   assert cleaned.errored_df['person_id'].tolist() == [2]

3. Validate and rename fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The model accepts the CSV header ``person_id`` as an input alias for ``id``.
With ``output='model'``, the successful DataFrame uses the model's serialized
column names, ready for the SQL table definition.

.. testcode:: pipeline

   from pydantic import BaseModel, Field

   class Person(BaseModel):
       id: int = Field(alias='person_id')
       name: str
       age: int = Field(ge=0)

   checked = validate(cleaned.success_df, Person, output='model')
   assert checked.errored_df['name'].tolist() == ['Grace']
   assert list(checked.success_df.columns) == ['id', 'name', 'age']

4. Create the table and load rows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pass a SQLAlchemy ``Table`` to create the table with a primary key. In
append mode, Abraxos rolls back a failed insert attempt before retrying
smaller batches. The duplicate ID stays in ``errored_df``.

.. testcode:: pipeline

   from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

   people = Table(
       'people',
       MetaData(),
       Column('id', Integer, primary_key=True),
       Column('name', String(100), nullable=False),
       Column('age', Integer, nullable=False),
   )
   engine = create_engine('sqlite://')
   try:
       with engine.begin() as connection:
           loaded = to_sql(checked.success_df, people.name, connection, table=people)
           stored = connection.execute(people.select()).all()
       assert loaded.errored_df['name'].tolist() == ['Duplicate']
       assert stored == [(1, 'Ada', 28)]
   finally:
       engine.dispose()

Inspect failures
----------------

Use ``bad_lines`` to inspect rejected CSV records. For the other stages,
inspect ``errored_df`` and ``errors`` together. A whole batch can fail with
one exception. An operation that cannot safely continue raises an exception.
For details, see the :doc:`stage guides <tutorials/index>`
and :doc:`API reference <api>`.
