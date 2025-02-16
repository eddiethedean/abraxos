import pandas as pd
import numpy as np


def split(
    df: pd.DataFrame,
    i: int = 2
) -> tuple[pd.DataFrame, ...]:
    """
    Splits a DataFrame into `i` approximately equal parts.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to be split.
    i : int, optional
        The number of parts to split the DataFrame into (default is 2).

    Returns
    -------
    tuple of pd.DataFrame
        A tuple containing `i` DataFrames, each being a partition of the original DataFrame.
    
    Examples
    --------
    >>> import pandas as pd
    >>> import abraxos
    >>> df = pd.DataFrame({'A': range(10)})
    >>> abraxos.split(df, 3)
    (   A
    0  0
    1  1
    2  2
    3  3,
     A
    4  4
    5  5
    6  6,
     A
    7  7
    8  8
    9  9)
    """
    return tuple(map(pd.DataFrame, np.array_split(df, i)))


def clear(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clear all rows from DataFrame.
    """
    return df.iloc[:0]


def to_records(df: pd.DataFrame) -> list[dict]:
    df = df.fillna(np.nan).replace([np.nan], [None])
    return df.to_dict('records')