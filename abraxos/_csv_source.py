"""Open CSV sources and close resources owned by the reader."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from io import BufferedIOBase, RawIOBase
from os import PathLike, fspath
from typing import IO, Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CsvSource = str | PathLike[str] | IO[str] | IO[bytes]


@contextmanager
def open_csv_source(
    path: CsvSource,
    *,
    compression: str | dict[str, Any] | None = 'infer',
    storage_options: dict[str, Any] | None = None,
    memory_map: bool = False,
    encoding: str | None = None,
    encoding_errors: str = 'strict',
) -> Iterator[tuple[str, Iterable[str]]]:
    """Yield the source name and text lines while reader-owned resources stay open."""
    source_name = (
        fspath(path)
        if isinstance(path, (str, PathLike))
        else str(getattr(path, 'name', '<stream>'))
    )
    # Use pandas' handle layer for URL, encoding, compression, and file ownership.
    # HTTP streams can bypass pandas' eager URL buffering unless an archive needs it.
    from pandas.io.common import (  # type: ignore[import-not-found]
        get_compression_method,
        get_handle,
        infer_compression,
    )

    source = fspath(path) if isinstance(path, PathLike) else path
    mode = 'rb' if isinstance(path, (BufferedIOBase, RawIOBase)) else 'r'
    with ExitStack() as stack:
        if isinstance(source, str) and urlsplit(source).scheme in ('http', 'https'):
            method, compression_options = get_compression_method(compression)
            method = infer_compression(source, method)
            if method not in ('zip', 'tar') and not memory_map:
                response = stack.enter_context(
                    urlopen(Request(source, headers=storage_options or {}))
                )
                mode = 'rb'
                source = response
                storage_options = None
                if response.headers.get('Content-Encoding') == 'gzip':
                    compression = 'gzip'
                else:
                    compression = dict(compression_options, method=method) if method else None

        handles = stack.enter_context(
            get_handle(
                source,
                mode,
                encoding=encoding,
                compression=compression,
                memory_map=memory_map,
                errors=encoding_errors,
                storage_options=storage_options,
            )
        )
        yield source_name, handles.handle
