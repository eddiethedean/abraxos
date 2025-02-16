from __future__ import annotations

import typing as t
import abc

import pandas as pd
import numpy as np

from abraxos import utils


class SqlInsert(t.Protocol):
    """Protocol for sqlalchemy.Insert object"""
    ...


class SqlConnection(t.Protocol):
    """Protocol for sqlalchemy.Connection object"""
    @abc.abstractmethod
    def execute(
        self,
        insert: SqlInsert,
        records: t.Iterable[dict]
    ):
        raise NotImplementedError
    
    
class SqlEngine(t.Protocol):
    """Protoocol for sqlalchemy.Engine object"""
    @abc.abstractmethod
    def connect(self) -> SqlConnection:
        raise NotImplementedError


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
    chunks: int = 2,
    **kwargs
) -> ToSqlResult:
    errors: list[Exception] = []
    errored_dfs: list[pd.DataFrame] = [utils.clear(df), ]
    success_dfs: list[pd.DataFrame] = [utils.clear(df), ]
    try:
        df.to_sql(name, con, if_exists=if_exists, index=index, method='multi', **kwargs)
        return ToSqlResult([], utils.clear(df), df)
    except Exception as e:
        if len(df) > 1:
            for df_chunk in utils.split(df, chunks):
                result: ToSqlResult = to_sql(
                    df_chunk,
                    name, con,
                    if_exists=if_exists,
                    index=index,
                    **kwargs
                )
                errors.extend(result.errors)
                errored_dfs.append(result.errored_df)
                success_dfs.append(result.success_df)
        else:
            try:
                df.to_sql(name, con, if_exists=if_exists, index=index, method='multi', **kwargs)
                return ToSqlResult([], utils.clear(df), df)
            except Exception as e:
                return ToSqlResult([e], df, utils.clear(df))

    return ToSqlResult(errors, pd.concat(errored_dfs), pd.concat(success_dfs))


def insert_df(
    df: pd.DataFrame,
    connection: SqlConnection,
    sql_query: SqlInsert
) -> ToSqlResult:
    records: list[dict] = utils.to_records(df)
    connection.execute(sql_query, records)
    return ToSqlResult([], utils.clear(df), df)


def use_sql(
    df: pd.DataFrame,
    connection: SqlConnection,
    sql_query: SqlInsert,
    chunks: int = 2
) -> ToSqlResult:
    """
    User provided SQL Insert to inser DataFrame records.
    """
    errors: list[Exception] = []
    errored_dfs: list[pd.DataFrame] = [utils.clear(df), ]
    success_dfs: list[pd.DataFrame] = [utils.clear(df), ]
    try:
        return insert_df(df, connection, sql_query)
    except Exception as e:
        if len(df) > 1:
            for df_chunk in utils.split(df, chunks):
                result: ToSqlResult = use_sql(df_chunk, connection, sql_query)
                errors.extend(result.errors)
                errored_dfs.append(result.errored_df)
                success_dfs.append(result.success_df)
        else:
            try:
                return insert_df(df, connection, sql_query)
            except Exception as e:
                return ToSqlResult([e], df, utils.clear(df))

    return ToSqlResult(
        errors,
        pd.concat(errored_dfs),
        pd.concat(success_dfs)
    )