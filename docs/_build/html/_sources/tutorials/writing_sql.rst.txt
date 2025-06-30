Writing DataFrames to SQL databases
===================================

Insert pandas DataFrames into SQL tables with retries and error tracking.

Example:

.. code-block:: python

    from abraxos import to_sql

    result = to_sql(df, "table_name", connection)
    print("Errors:", result.errors)
    print("Successful Inserts:", result.success_df.shape[0])
