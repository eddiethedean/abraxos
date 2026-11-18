# Abraxos

[![PyPI version](https://img.shields.io/pypi/v/abraxos.svg?style=flat)](https://pypi.org/project/abraxos/)
[![Documentation status](https://readthedocs.org/projects/abraxos/badge/?version=latest)](https://abraxos.readthedocs.io/en/latest/)
[![CI](https://github.com/eddiethedean/abraxos/actions/workflows/ci.yml/badge.svg)](https://github.com/eddiethedean/abraxos/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat)](https://github.com/eddiethedean/abraxos/blob/main/LICENSE.txt)

Abraxos helps you build pandas ETL pipelines that can keep processing after a row fails. Read CSVs, transform and validate DataFrames, and load them into SQL while keeping rejected records available for inspection.

[Documentation](https://abraxos.readthedocs.io/en/latest/) · [API reference](https://abraxos.readthedocs.io/en/latest/api.html) · [Upgrade guide](https://abraxos.readthedocs.io/en/latest/upgrading.html)

## Installation

Abraxos requires **Python 3.11+** and **pandas 2.3.3+**, including pandas 3.x.

```bash
uv venv --python 3.11
uv pip install abraxos
```

The base package includes CSV reading, transformations, and DataFrame utilities. Install the optional integrations for SQLAlchemy and Pydantic as needed. Both extras are used by the example below.

```bash
uv pip install 'abraxos[sql,validate]'
```

The same package names and extras work with `python -m pip install` in an activated virtual environment. The `sql` extra installs SQLAlchemy 2.0.44 or later, and `validate` installs Pydantic 2.12 or later.

## Quick start

This pipeline reads a CSV, trims names, validates ages, and creates a SQLite table with a primary key. The sample includes one rejected record at each of the CSV, validation, and SQL stages.

```python
from io import StringIO

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from abraxos import read_csv, to_sql, transform, validate

source = StringIO(
    'person_id,name,age\n1, Ada ,28\noops,too,many,fields\n2, Grace ,invalid\n1, Duplicate ,34\n'
)
extracted = read_csv(source)
cleaned = transform(extracted.dataframe, lambda batch: batch.assign(name=batch['name'].str.strip()))


class Person(BaseModel):
    id: int = Field(alias='person_id')
    name: str
    age: int = Field(ge=0)


checked = validate(cleaned.success_df, Person, output='model')
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
        stored = connection.execute(people.select().order_by(people.c.id)).all()
finally:
    engine.dispose()

print('CSV rejections:', extracted.bad_lines)
print('Validation rejections:', checked.errored_df['name'].tolist())
print('SQL rejections:', loaded.errored_df['name'].tolist())
print('Stored people:', stored)
```

```text
CSV rejections: [['oops', 'too', 'many', 'fields']]
Validation rejections: ['Grace']
SQL rejections: ['Duplicate']
Stored people: [(1, 'Ada', 28)]
```

## Working with results

| Operation | Result and recovery behavior |
| --- | --- |
| `read_csv(source)` | `dataframe` contains accepted records. `bad_lines` contains records with the wrong number of fields. A CSV syntax error that prevents recovery raises `CsvParseError` with its source and starting line. |
| `read_csv(source, chunksize=1000)` | Produces the same result type for each chunk. Rejected records count toward `chunksize`. Pass `dtype` for consistent conversion across chunks. |
| `transform(df, callback)` | Retries failed batches on smaller partitions. Pass `split_on_error=False` for operations such as ranking or normalization that need the entire frame. |
| `validate(df, Model)` | Maps validated values to input columns by default. Pass `output='model'` for serialized fields and defaults, or `column_map` for an explicit input-to-output mapping. |
| `to_sql(df, name, con)` | Rolls back and retries recoverable append failures on SQLAlchemy SQLite and PostgreSQL connections. Pass `table=` to define the schema for a new table. |
| `use_sql(df, con, insert)` | Executes a supplied insert statement and leaves the SQLAlchemy transaction open for the caller to commit or roll back. |

`transform`, `validate`, `to_sql`, and `use_sql` return `success_df`, `errored_df`, and `errors`. Terminal SQL failures raise `LoadError`. A raw `sqlite3.Connection` supports one standalone write with autocommit disabled. Use SQLAlchemy for transactional retries and table replacement.

## Development

```bash
uv sync --locked
uv run --locked pytest
uv run --locked sphinx-build -W -b html docs docs/_build/html
uv run --locked sphinx-build -W -b doctest docs docs/_build/doctest
```

See the [contribution guide](https://github.com/eddiethedean/abraxos/blob/main/CONTRIBUTING.md) for linting, type checks, and PostgreSQL integration tests. See the [changelog](https://github.com/eddiethedean/abraxos/blob/main/CHANGELOG.md) for release history. Abraxos is maintained by [Odos Matthews](https://github.com/eddiethedean) and licensed under [MIT](https://github.com/eddiethedean/abraxos/blob/main/LICENSE.txt).
