import typing as t
import collections.abc as a

import pandas as pd
import sqlalchemy as sa

from . import split
from . import fill


class ToSqlResult(t.NamedTuple):
    errors: list
    errored_dfs: pd.DataFrame
    success_dfs: pd.DataFrame
 

def to_sql(
    df: pd.DataFrame,
    name: str,
    con: sa.engine.Connection | sa.engine.Engine,
    *,
    if_exists='append',
    index=False,
    **kwargs
) -> ToSqlResult:
    errors: list = [Exception]
    errored_dfs = [df[0:0], ]
    success_dfs = [df[0:0], ]
    try:
        df.to_sql(name, con, if_exists=if_exists, index=index, method='multi', **kwargs)
        return ToSqlResult([], df[0:0], df)
    except Exception as e:
        if len(df) > 1:
            df1, df2 = split.split_df(df)
            errors1, errored_df1, success_df1 = to_sql(df1, name, con, if_exists=if_exists, index=index, **kwargs)
            errors2, errored_df2, success_df2 = to_sql(df2, name, con, if_exists=if_exists, index=index, **kwargs)
            errors.extend(errors1 + errors2)
            errored_dfs.extend([errored_df1, errored_df2])
            success_dfs.extend([success_df1, success_df2])
        else:
            try:
                df.to_sql(name, con, if_exists=if_exists, index=index, method='multi', **kwargs)
                return ToSqlResult([], df[0:0], df)
            except Exception as e:
                return ToSqlResult([e], df, df[0:0])

    return ToSqlResult(errors, pd.concat(errored_dfs), pd.concat(success_dfs))


def to_records(df: pd.DataFrame) -> list[dict]:
    return [fill.fill_nans(record, None) for record in df.to_dict('records')]


def insert_df(
    df: pd.DataFrame,
    connection: sa.engine.Connection,
    sql_query: sa.Insert
) -> ToSqlResult:
    records = to_records(df)
    connection.execute(sql_query, records)
    return ToSqlResult([], df[0:0], df)


def use_sql(
    df: pd.DataFrame,
    connection: sa.engine.Connection,
    sql_query: sa.Insert
) -> ToSqlResult:
    """
    User user provided SQL Insert to inser DataFrame records.
    """
    errors: list = [Exception]
    errored_dfs: list[pd.DataFrame] = [df[0:0], ]
    success_dfs: list[pd.DataFrame] = [df[0:0], ]
    try:
        return insert_df(df, connection, sql_query)
    except Exception as e:
        if len(df) > 1:
            df1, df2 = split.split_df(df)
            errors1, errored_df1, success_df1 = use_sql(df1, connection, sql_query)
            errors2, errored_df2, success_df2 = use_sql(df2, connection, sql_query)
            errors.extend(errors1 + errors2)
            errored_dfs.extend([errored_df1, errored_df2])
            success_dfs.extend([success_df1, success_df2])
        else:
            try:
                return insert_df(df, connection, sql_query)
            except Exception as e:
                return ToSqlResult([e], df, df[0:0])

    return ToSqlResult(errors, pd.concat(errored_dfs), pd.concat(success_dfs))