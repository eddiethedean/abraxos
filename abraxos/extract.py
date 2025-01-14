import collections.abc as a
import typing as t

import pandas as pd


class ReadCsvResult(t.NamedTuple):
    bad_lines: list[list[str]]
    dataframe: pd.DataFrame
    

def read_csv_chunks(
    path: str,
    chunksize: int,
    **kwargs
) -> a.Generator[ReadCsvResult, None, None]:
    """
    Reads a CSV file in chunks and captures bad lines separately.

    Parameters
    ----------
    path : str
        Path to the CSV file.
    chunksize : int
        Number of rows per chunk.
    **kwargs : dict
        Additional arguments for `pandas.read_csv`.

    Yields
    ------
    ReadCsvResult
        A named tuple containing bad lines and the corresponding DataFrame chunk.

    Example
    -------
    >>> import abraxos

    >>> for bad_lines, df in abraxos.read_csv_chunks('bad.csv', 4):
    ...     print(bad_lines)
    ...     print(df)
    [['', '', '', 'd', '', 'f', '', '', '', '', 'f', '', '', '', '']]
        id  name    age
    0   1   Joe     38
    1   2   James   31
    2   3   Jordon  2
    [['', 'f', 'f', '5', '6', '7', '8']]
        id  name    age
    3   2   Jasper  31
    4   1   Jill    38
    """
    bad_lines: list[list[str]] = []
    kwargs.update({"on_bad_lines": bad_lines.append, "engine": "python"})
    
    chunks = pd.read_csv(path, chunksize=chunksize, **kwargs)
    for chunk in chunks:
        yield ReadCsvResult(bad_lines.copy(), chunk)
        bad_lines.clear()


def read_csv(
    path: str,
    *,
    chunksize: int | None = None,
    **kwargs
) -> ReadCsvResult | a.Generator[ReadCsvResult, None, None]:
    """
    Reads a CSV file and captures bad lines separately.

    Parameters
    ----------
    path : str
        Path to the CSV file.
    chunksize : int, optional
        Number of rows per chunk. If None, reads the entire file at once.
    **kwargs : dict
        Additional arguments for `pandas.read_csv`.

    Returns
    -------
    ReadCsvResult or Generator
        If `chunksize` is specified, returns a generator yielding `ReadCsvResult`,
        otherwise returns a single `ReadCsvResult`.
    Example
    -------
    >>> import abraxos

    >>> bad_lines, good_df = abraxos.read_csv('people.csv')
    >>> bad_lines
    [['', '', '', 'd', '', 'f', '', '', '', '', 'f', '', '', '', ''],
    ['', 'f', 'f', '5', '6', '7', '8']]
    >>> good_df
        id   name    age
    0   1    Joe     38
    1   2    James   31
    2   3    Jordon  2
    3   2    Jasper  31
    4   1    Jill    38
    """
    if chunksize is not None:
        return read_csv_chunks(path, chunksize, **kwargs)
        
    bad_lines: list[list[str]] = []
    kwargs.update({"on_bad_lines": bad_lines.append, "engine": "python"})
    
    df = pd.read_csv(path, **kwargs)
    return ReadCsvResult(bad_lines, df)