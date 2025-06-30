Transforming DataFrames with abraxos
===================================

Apply transformations to pandas DataFrames with error handling.

Example:

.. code-block:: python

    from abraxos import transform

    def clean_data(df):
        df["column"] = df["column"].str.lower()
        return df

    result = transform(df, clean_data)
    print("Errors:", result.errors)
    print("Transformed Data:", result.success_df.head())
