:hide-toc:

.. rst-class:: ab-home

Row-level recovery for pandas pipelines
=======================================

.. rst-class:: ab-lead

Read CSVs, transform and validate DataFrames, and load accepted rows into
SQL. Abraxos lets you inspect what each stage rejected.

.. container:: ab-actions

   :doc:`Run the quick start <quickstart>`

   :doc:`Browse the API <api>`

.. container:: ab-install

   .. container:: ab-install-details

      **Install Abraxos**

      Python 3.11+ and pandas 2.3.3+

   .. code-block:: bash

      uv venv --python 3.11
      uv pip install abraxos

Pipeline guides
---------------

.. container:: ab-stage-grid

   .. container:: ab-stage

      :doc:`Read CSVs <tutorials/reading_csv>`

      Collect malformed records and process large files in chunks.

   .. container:: ab-stage

      :doc:`Transform DataFrames <tutorials/transforming_data>`

      Isolate rows that fail a transformation.

   .. container:: ab-stage

      :doc:`Validate with Pydantic <tutorials/validating_data>`

      Coerce values and choose the output schema.

   .. container:: ab-stage

      :doc:`Load SQL tables <tutorials/writing_sql>`

      Define primary keys and recover from row errors during inserts.

:doc:`Upgrading from Abraxos 0.1? <upgrading>`

.. toctree::
   :hidden:
   :maxdepth: 2

   quickstart
   tutorials/index
   upgrading
   api
