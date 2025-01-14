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
    bad_lines = []
    
    def store_bad_line(bad_line):
        bad_lines.append(bad_line)

    kwargs['on_bad_lines'] = store_bad_line
    kwargs['engine'] = 'python'
    
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
    if chunksize:
        return read_csv_chunks(path, chunksize, **kwargs)
        
    bad_lines = []
    
    def store_bad_line(bad_line):
        bad_lines.append(bad_line)

    kwargs['on_bad_lines'] = store_bad_line
    kwargs['engine'] = 'python'
    
    df = pd.read_csv(path, **kwargs)
    return ReadCsvResult(bad_lines, df)