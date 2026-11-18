"""Custom exceptions for the abraxos package."""

from __future__ import annotations


class AbraxosError(Exception):
    """Base exception for all abraxos errors."""

    pass


class TransformError(AbraxosError):
    """Exception raised when DataFrame transformation fails."""

    pass


class ValidationError(AbraxosError):
    """A validation operation cannot produce a reliable result."""

    pass


class LoadError(AbraxosError):
    """A SQL load cannot complete or reliably account for its writes."""

    pass


class CsvParseError(AbraxosError):
    """A CSV reader cannot reliably locate the next record boundary."""

    def __init__(self, source: str, line: int, message: str) -> None:
        self.source = source
        self.line = line
        super().__init__(f'{source}, line {line}: {message}')


__all__ = ['AbraxosError', 'CsvParseError', 'TransformError', 'ValidationError', 'LoadError']
