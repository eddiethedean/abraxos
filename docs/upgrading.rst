Upgrade from 0.1 to 0.2
=======================

Update dependencies
-------------------

Abraxos 0.2 requires Python 3.11 or later and pandas 2.3.3 or later. The
``sql`` extra requires SQLAlchemy 2.0.44 or later, and the ``validate``
extra requires Pydantic 2.12 or later. Projects that depend on pandas dtype
inference can specify ``dtype`` explicitly, especially for CSV chunks.

Review CSV reader options
-------------------------

- Short and long records appear in ``bad_lines``. Width is checked before
  column selection, including for the first data record.
- Use a one-character separator or a CSV dialect and a single header row.
  Abraxos controls the parser and bad-line policy. For regex separators or
  multi-row headers, parse with pandas and pass the resulting DataFrame to
  the downstream stages.
- Handle :exc:`~abraxos.exceptions.CsvParseError` around the read or chunk
  iterator. Its ``source`` and ``line`` identify the record where parsing
  stopped.

Review transforms and validation
--------------------------------

- Use ``split_on_error=False`` for callbacks that need the full DataFrame.
  Callbacks now receive isolated batches and must return a DataFrame.
- Rename duplicate column labels before validation, record conversion, or
  SQL loading. The record conversion helpers require unique labels.
- Input-aligned validation keeps recognized Pydantic aliases under their
  original input labels. Use ``output='model'`` for serialized field names
  and defaults. Supply ``column_map`` for ambiguous mappings.
- ``split()`` returns independent DataFrame partitions for assignments.
  Mutable Python objects nested inside the cells of those partitions are
  still shared.

Review SQL failure handling
---------------------------

- Disable driver autocommit. Use a SQLAlchemy engine or connection for
  transactional replacement and row-level retries on SQLite and PostgreSQL.
  Raw SQLite connections support one standalone append or create attempt
  with no active caller transaction.
- Handle :exc:`~abraxos.exceptions.LoadError` for operation-wide failures,
  including connection outages and lost transactions. Inspect ``errors``
  and ``errored_df`` for recoverable failures returned by a completed call.
- Commit or roll back caller-owned transactions, including those opened by
  ``use_sql()``. An engine-owned load commits once.
- For a custom ``use_sql()`` adapter, supply ``retry_if`` to identify row
  errors eligible for splitting. The adapter must roll back each failed
  attempt before requesting recovery.

See the :doc:`pipeline guides <tutorials/index>` for examples using the new
behavior.
