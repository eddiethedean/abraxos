import collections.abc as a
import typing as t

import pandas as pd

from . import split
 

class TransformResult(t.NamedTuple):
    errors: list[Exception]
    errored_df: pd.DataFrame
    success_df: pd.DataFrame


def transform(
    df: pd.DataFrame,
    transformer: a.Callable[[pd.DataFrame], pd.DataFrame]
) -> TransformResult:
    errors = []
    errored_dfs = []
    success_dfs = []
    try:
        return TransformResult([], df[0:0], transformer(df))
    except Exception as e:
        if len(df) > 1:
            df1, df2 =  split.split_df(df)
            errors1, e_df1, s_df1 = transform(df1, transformer)
            errors2, e_df2, s_df2 = transform(df2, transformer)
            errors.extend(errors1 + errors2)
            errored_dfs.extend([e_df1, e_df2])
            success_dfs.extend([s_df1, s_df2])
        else:
            try:
                return TransformResult([], df[0:0], transformer(df))
            except Exception as e:
                return TransformResult([e], df, df[0:0])
            
    errored_df = pd.concat(errored_dfs)
    success_df = pd.concat(success_dfs)
    return TransformResult(errors, errored_df, success_df)