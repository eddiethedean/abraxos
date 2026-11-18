Read CSVs and inspect rejected records
======================================

Read at once
------------

:func:`~abraxos.extract.read_csv` accepts a path or a file-like object. It
checks each record against the header or explicit ``names`` before pandas
applies column selection and type conversion. The result's ``bad_lines``
contains both short and long records as lists of fields.

.. testcode:: csv-full

   from io import StringIO

   from abraxos import read_csv

   source = StringIO('id,name\nEXTRA,1,Alice\n2,Bob\n3\n')
   result = read_csv(source)
   assert result.bad_lines == [['EXTRA', '1', 'Alice'], ['3']]
   assert result.dataframe.to_dict('records') == [{'id': 2, 'name': 'Bob'}]

Use ``names`` to declare the width of a headerless file. With
``header=None`` and no names, the first logical record determines the width.
Use a one-character separator or a CSV dialect and a single header row.
Abraxos controls ``engine`` and ``on_bad_lines``. Pandas conversion options
such as ``usecols``, ``index_col``, ``dtype``, and ``parse_dates`` apply to
accepted records.

Stream chunks
-------------

``chunksize`` counts input records, including rejected ones. A record can
span multiple physical lines inside a quoted field. A chunk can contain
only rejections, so check ``bad_lines`` even when ``dataframe`` is empty.
Set ``dtype`` when values should have the same type in every chunk.

.. testcode:: csv-chunks

   from contextlib import closing
   from io import StringIO

   from abraxos import read_csv

   source = StringIO('id,name\n1,Ada\n2\n3,"Grace\nHopper"\n')
   with closing(read_csv(source, chunksize=1, dtype={'id': 'Int64'})) as records:
       first, rejected, last = records

   assert first.dataframe['id'].tolist() == [1]
   assert rejected.dataframe.empty
   assert rejected.bad_lines == [['2']]
   assert last.dataframe['name'].tolist() == ['Grace\nHopper']

Exhaust the generator or close it when you stop early. Abraxos closes
resources it opened. A stream supplied by the caller stays open.

Handle malformed quoting
------------------------

If CSV syntax makes record boundaries unreliable, the reader raises
:exc:`~abraxos.exceptions.CsvParseError`. Its ``source`` and ``line``
attributes identify the input and the starting physical line of the record.
With chunked reads, the exception is raised when iteration reaches the error.

.. testcode:: csv-syntax

   from io import StringIO

   from abraxos import CsvParseError, read_csv

   try:
       read_csv(StringIO('id,name\n1,Ada\n2,"Unclosed\n'))
   except CsvParseError as error:
       assert error.source == '<stream>'
       assert error.line == 3
   else:
       raise AssertionError('Expected a CSV syntax error')
