API reference
=============

Import functions and result types from ``abraxos``. This reference groups
functions by pipeline stage and lists the fields on their result types.

CSV extraction
--------------

.. autosummary::
   :toctree: _autosummary
   :template: api-object.rst
   :nosignatures:

   ~abraxos.extract.read_csv
   ~abraxos.extract.read_csv_chunks
   ~abraxos.extract.ReadCsvResult

Transformation
--------------

.. autosummary::
   :toctree: _autosummary
   :template: api-object.rst
   :nosignatures:

   ~abraxos.transform.transform
   ~abraxos.transform.TransformResult

Validation
----------

.. autosummary::
   :toctree: _autosummary
   :template: api-object.rst
   :nosignatures:

   ~abraxos.validate.validate
   ~abraxos.validate.ValidateResult

SQL loading
-----------

.. autosummary::
   :toctree: _autosummary
   :template: api-object.rst
   :nosignatures:

   ~abraxos.load.to_sql
   ~abraxos.load.use_sql
   ~abraxos.load.ToSqlResult

DataFrame utilities
-------------------

.. autosummary::
   :toctree: _autosummary
   :template: api-object.rst
   :nosignatures:

   ~abraxos.utils.split
   ~abraxos.utils.clear
   ~abraxos.utils.to_records

Exceptions
----------

.. autosummary::
   :toctree: _autosummary
   :template: api-object.rst
   :nosignatures:

   ~abraxos.exceptions.AbraxosError
   ~abraxos.exceptions.CsvParseError
   ~abraxos.exceptions.LoadError
   ~abraxos.exceptions.ValidationError
   ~abraxos.exceptions.TransformError
