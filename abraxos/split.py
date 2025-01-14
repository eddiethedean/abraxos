import pandas as pd


def split_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mid = int(len(df)/2)
    return df.iloc[:mid], df.iloc[mid:]