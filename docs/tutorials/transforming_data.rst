Transform DataFrames with row recovery
======================================

Isolate a failed row
--------------------

:func:`~abraxos.transform.transform` calls your function with a copy of the
batch, including mutable objects stored in object cells. The function
returns a DataFrame and raises when it encounters data it cannot process.
Abraxos splits a failed batch and retries each part. A row that still fails
on its own goes into ``errored_df`` with the original data.

.. testcode:: transform-rows

   import pandas as pd

   from abraxos import transform

   def unit_price(batch):
       if batch['units'].eq(0).any():
           raise ValueError('Units must be nonzero')
       return batch.assign(unit_price=batch['total'] / batch['units'])

   orders = pd.DataFrame({'units': [4, 0, 2], 'total': [20, 10, 4]}, index=['a', 'b', 'c'])
   result = transform(orders, unit_price)
   assert result.success_df['unit_price'].to_dict() == {'a': 5.0, 'c': 2.0}
   assert result.errored_df.index.tolist() == ['b']
   assert str(result.errors[0]) == 'Units must be nonzero'

Splitting works when each row's result is independent of the rest of the
batch. A callback can run on several overlapping batches during recovery,
so keep external writes and other side effects outside it.

Keep the frame together
-----------------------

Use ``split_on_error=False`` for operations that need all rows, such as
ranking or normalization. If the callback raises in this mode, the result
contains one error and the original frame in ``errored_df``.

.. testcode:: transform-frame

   import pandas as pd

   from abraxos import transform

   prices = pd.DataFrame({'price': [5, 10, 15]})
   result = transform(
       prices,
       lambda batch: batch.assign(centered=batch['price'] - batch['price'].mean()),
       split_on_error=False,
   )
   assert result.success_df['centered'].tolist() == [-5.0, 0.0, 5.0]
