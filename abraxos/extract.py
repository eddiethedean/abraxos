import collections.abc as a
import typing as t
from typing import Optional, Union

import pandas as pd


class ReadCsvResult(t.NamedTuple):
    """
    A named tuple representing the result of reading a CSV file.

    Attributes
    ----------
    bad_lines : list of list of str
        List of lines that could not be parsed correctly.
    dataframe : pandas.DataFrame
        Parsed portion of the CSV file.
    """
    bad_lines: t.List[t.List[str]]
    dataframe: pd.DataFrame


def read_csv_chunks(
    path: str,
    chunksize: int,
    **kwargs
) -> a.Generator[ReadCsvResult, None, None]:
    """
    Reads a CSV file in chunks and captures malformed lines.

    Parameters
    ----------
    path : str
        Path to the CSV file.
    chunksize : int
        Number of rows per chunk.
    **kwargs : dict
        Additional arguments passed to `pandas.read_csv`.

    Yields
    ------
    ReadCsvResult
        A named tuple containing bad lines and the parsed DataFrame for the chunk.

    Examples
    --------
    >>> for result in read_csv_chunks('data.csv', chunksize=100):
    ...     print(result.bad_lines)
    ...     print(result.dataframe)
    """
    bad_lines: t.List[t.List[str]] = []
    kwargs.update({"on_bad_lines": bad_lines.append, "engine": "python"})

    chunks = pd.read_csv(path, chunksize=chunksize, **kwargs)
    for chunk in chunks:
        yield ReadCsvResult(bad_lines.copy(), chunk)
        bad_lines.clear()


def read_csv_all(
    path: str,
    **kwargs
) -> ReadCsvResult:
    """
    Reads an entire CSV file and captures malformed lines.

    Parameters
    ----------
    path : str
        Path to the CSV file.
    **kwargs : dict
        Additional arguments passed to `pandas.read_csv`.

    Returns
    -------
    ReadCsvResult
        A named tuple containing bad lines and the parsed DataFrame.

    Examples
    --------
    >>> result = read_csv_all('data.csv')
    >>> print(result.bad_lines)
    >>> print(result.dataframe)
    """
    bad_lines: t.List[t.List[str]] = []
    kwargs.update({"on_bad_lines": bad_lines.append, "engine": "python"})
    df: pd.DataFrame = pd.read_csv(path, **kwargs)
    return ReadCsvResult(bad_lines, df)


def read_csv(
    path: str,
    *,
    chunksize: Optional[int] = None,
    **kwargs
) -> Union[ReadCsvResult, a.Generator[ReadCsvResult, None, None]]:
    """
    Reads a CSV file and optionally processes it in chunks, capturing malformed lines.

    Parameters
    ----------
    path : str
        Path to the CSV file.
    chunksize : int, optional
        Number of rows per chunk. If specified, the file is read in chunks.
        If None (default), the entire file is read at once.
    **kwargs : dict
        Additional arguments passed to `pandas.read_csv`.

    Returns
    -------
    ReadCsvResult or Generator of ReadCsvResult
        If `chunksize` is None, returns a single ReadCsvResult.
        Otherwise, returns a generator yielding ReadCsvResult for each chunk.

    Examples
    --------
    >>> result = read_csv('data.csv')
    >>> print(result.bad_lines)
    >>> print(result.dataframe)

    >>> for result in read_csv('data.csv', chunksize=50):
    ...     print(result.bad_lines)
    ...     print(result.dataframe)
    """
    if chunksize is not None:
        return read_csv_chunks(path, chunksize, **kwargs)
    return read_csv_all(path, **kwargs)
