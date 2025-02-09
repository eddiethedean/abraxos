from __future__ import annotations

import typing as t
import abc

import pandas as pd
import numpy as np

from abraxos import split


class SqlInsert(t.Protocol):
    """Protocol for sqlalchemy.Insert object"""
    ...


class Connectable(t.Protocol):
    def connect(self) -> SqlConnection:
        raise NotImplementedError


class SqlConnection(Connectable):
    """Protocol for sqlalchemy.Connection object"""
    @abc.abstractmethod
    def execute(
        self,
        insert: SqlInsert,
        records: t.Iterable[dict]
    ):
        raise NotImplementedError
    
    
class SqlEngine(Connectable):
    """Protoocol for sqlalchemy.Engine object"""
    ...


class ToSqlResult(t.NamedTuple):
    errors: list
    errored_df: pd.DataFrame
    success_df: pd.DataFrame
 

def to_sql(
    df: pd.DataFrame,
    name: str,
    con: SqlConnection | SqlEngine,
    *,
    if_exists: t.Literal['fail', 'replace', 'append'] = 'append',
    index: bool = False,
    **kwargs
) -> ToSqlResult:
    errors: list[Exception] = []
    errored_dfs: list[pd.DataFrame] = [df[0:0], ]
    success_dfs: list[pd.DataFrame] = [df[0:0], ]
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
    df = df.fillna(np.nan).replace([np.nan], [None])
    return df.to_dict('records')


def insert_df(
    df: pd.DataFrame,
    connection: SqlConnection,
    sql_query: SqlInsert
) -> ToSqlResult:
    records: list[dict] = to_records(df)
    connection.execute(sql_query, records)
    return ToSqlResult([], df[0:0], df)


def use_sql(
    df: pd.DataFrame,
    connection: SqlConnection,
    sql_query: SqlInsert
) -> ToSqlResult:
    """
    User user provided SQL Insert to inser DataFrame records.
    """
    errors: list[Exception] = []
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