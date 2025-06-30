Reading CSV files with abraxos
==============================

Abraxos provides functions to read CSV files robustly, handling bad lines and chunking.

Example:

.. code-block:: python

    from abraxos import read_csv

    bad_lines, df = read_csv("data.csv")
    print("Bad lines:", bad_lines)
    print(df.head())

Output:

.. code-block:: none

    Bad lines: [['', '', '', 'd', '', 'f', '', '', '', '', 'f', '', '', '', ''],
               ['', 'f', 'f', '5', '6', '7', '8']]
    <DataFrame output here>
