import collections.abc as a
import typing as t

import pandas as pd

from abraxos import utils
 

class TransformResult(t.NamedTuple):
    errors: list[Exception]
    errored_df: pd.DataFrame
    success_df: pd.DataFrame


def transform(
    df: pd.DataFrame,
    transformer: a.Callable[[pd.DataFrame], pd.DataFrame],
    chunks: int = 2
) -> TransformResult:
    """
    Recursively applies a transformation function to a DataFrame, handling errors gracefully.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to be transformed.
    transformer : Callable[[pd.DataFrame], pd.DataFrame]
        A function that takes a DataFrame and returns a transformed DataFrame.
    i_chunks : int, optional
        The number of chunks to split the DataFrame into when an error occurs (default is 2).

    Returns
    -------
    TransformResult
        A named tuple containing:
        - errors: A list of exceptions encountered during transformation.
        - errored_df: A DataFrame containing the rows that caused errors.
        - success_df: A DataFrame containing successfully transformed rows.

    Examples
    --------
    >>> import pandas as pd
    >>> def sample_transformer(df):
    ...     df['value'] = df['value'] * 2
    ...     return df
    >>> df = pd.DataFrame({'value': [1, 2, 3]})
    >>> transform(df, sample_transformer)
    TransformResult(errors=[], errored_df=Empty DataFrame
    Columns: [value]
    Index: [], success_df=   value
    0      2
    1      4
    2      6)
    """
    errors: list[Exception] = []
    errored_dfs: list[pd.DataFrame] = []
    success_dfs: list[pd.DataFrame] = []
    
    try:
        return TransformResult([], utils.clear(df), transformer(df))
    except Exception as e:
        if len(df) > 1:
            for df_c in utils.split(df, chunks):
                result: TransformResult = transform(df_c, transformer)
                errors.extend(result.errors)
                errored_dfs.append(result.errored_df)
                success_dfs.append(result.success_df)
        else:
            try:
                return TransformResult([], utils.clear(df), transformer(df))
            except Exception as e:
                return TransformResult([e], df, utils.clear(df))
    
    return TransformResult(
        errors,
        pd.concat(errored_dfs),
        pd.concat(success_dfs)
    )
