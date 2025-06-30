Validating Data with Pydantic Models
====================================

Use Pydantic models to validate pandas DataFrame rows.

Example:

.. code-block:: python

    from abraxos import validate
    from pydantic import BaseModel

    class MyModel(BaseModel):
        column: str

    result = validate(df, MyModel())
    print("Errors:", result.errors)
    print("Valid Data:", result.success_df.head())
