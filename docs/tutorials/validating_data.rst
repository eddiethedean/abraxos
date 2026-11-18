Validate rows with Pydantic
===========================

Choose the output schema
------------------------

:func:`~abraxos.validate.validate` passes each row to ``model_validate`` and
writes accepted values from ``model_dump``. Column labels must be unique.
The validator receives a copy of each row's values, including nested objects.
Failed rows retain their original values and indexes. Successful rows keep
their source indexes and contain the validated values, which may have new types.

.. testcode:: validate-shape

   import pandas as pd
   from pydantic import BaseModel, Field

   from abraxos import validate

   class Item(BaseModel):
       id: int = Field(alias='External ID')
       active: bool = True

   source = pd.DataFrame({'External ID': ['123', 'invalid']}, index=['a', 'b'])
   result = validate(source, Item)
   assert result.success_df.loc['a', 'External ID'] == 123
   assert result.errored_df.loc['b', 'External ID'] == 'invalid'
   assert len(result.errors) == 1

   serialized = validate(source, Item, output='model')
   assert serialized.success_df.to_dict('records') == [{'id': 123, 'active': True}]

The default ``output='input'`` keeps input columns and maps recognized
aliases back to their source labels. Deliberately excluded or ignored
columns have missing values. Use ``output='model'`` when the next stage
expects the model's serialized field names, defaults, or computed fields.

Map custom or nested fields
---------------------------

For input-aligned output, use ``column_map`` when a nested validation alias
or custom serializer makes the mapping ambiguous. Each key is an input
column label and each value is a serialized field key.

.. testcode:: validate-nested

   import pandas as pd
   from pydantic import AliasPath, BaseModel, Field

   from abraxos import validate

   class Item(BaseModel):
       id: int = Field(validation_alias=AliasPath('payload', 'id'))

   source = pd.DataFrame({'payload': [{'id': '123'}]})
   result = validate(source, Item, column_map={'payload': 'id'})
   assert result.success_df['payload'].tolist() == [123]

An ambiguous mapping or a missing explicitly mapped key raises
:exc:`~abraxos.exceptions.ValidationError`. So does a computed field or allowed
extra sharing another serialized field's key. With Pydantic's default
serialization, an allowed extra can use the alias of a field omitted by
``exclude_if`` for that row. Individual row validation errors appear in
``result.errors``.
