"""Scan logical CSV records and report physical line numbers."""

from __future__ import annotations

import csv
from _csv import Dialect
from collections.abc import Callable, Iterable, Iterator

from .exceptions import CsvParseError


class _CsvLines(Iterator[str]):
    """Physical input lines with record-boundary filtering and line tracking."""

    def __init__(
        self,
        lines: Iterable[str],
        dialect: Dialect,
        skip: Callable[[int], bool],
        skip_blanks: bool,
        comment: str | None,
    ) -> None:
        self.lines = iter(lines)
        self.dialect = dialect
        self.skip = skip
        self.skip_blanks = skip_blanks
        self.comment = comment
        self.line = 0
        self.start_record()

    def start_record(self) -> None:
        self.record_line = 0
        self.in_quotes = False
        self.at_field_start = True

    def __next__(self) -> str:
        for line in self.lines:
            self.line += 1
            if self.line == 1:
                line = line.removeprefix('\ufeff')
            if not self.record_line:
                if self.skip(self.line - 1):
                    continue
                if self.comment is not None and line.lstrip().startswith(self.comment):
                    continue
                if self.skip_blanks and not line.strip():
                    continue
                self.record_line = self.line
            return self._remove_inline_comment(line, self.comment) if self.comment else line
        raise StopIteration

    def _remove_inline_comment(self, line: str, comment: str) -> str:
        dialect = self.dialect
        quote = dialect.quotechar if dialect.quoting != csv.QUOTE_NONE else None
        position = 0
        while position < len(line):
            char = line[position]
            if char == dialect.escapechar:
                self.at_field_start = False
                position += 2
                continue
            if self.in_quotes:
                if char == quote:
                    if dialect.doublequote and line[position + 1 : position + 2] == quote:
                        position += 2
                        continue
                    self.in_quotes = False
            elif char == comment:
                return line[:position] + '\n'
            elif char == dialect.delimiter:
                self.at_field_start = True
            elif self.at_field_start:
                if char == quote:
                    self.in_quotes = True
                if char != ' ' or not dialect.skipinitialspace:
                    self.at_field_start = False
            position += 1
        return line


def scan_records(
    lines: Iterable[str],
    source: str,
    dialect: Dialect,
    skip_rows: Callable[[int], bool],
    skip_blank_lines: bool,
    comment: str | None,
) -> Iterator[list[str]]:
    """Read logical records and attach the source's physical line to syntax errors."""
    physical_lines = _CsvLines(lines, dialect, skip_rows, skip_blank_lines, comment)
    reader = csv.reader(physical_lines, dialect, strict=True)
    while True:
        physical_lines.start_record()
        try:
            row = next(reader)
        except StopIteration:
            return
        except csv.Error as error:
            line = physical_lines.record_line or physical_lines.line
            raise CsvParseError(source, line, str(error)) from error
        yield row
