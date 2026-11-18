"""Map serialized model output to the requested row shape."""

from __future__ import annotations

from collections import Counter
from collections.abc import Container, Hashable, Mapping
from typing import Any, Literal, NamedTuple

from .exceptions import ValidationError


class FieldProjection(NamedTuple):
    name: str
    input_paths: list[tuple[str | int, ...]]
    output_keys: tuple[str, ...]
    excluded: bool
    conditionally_excluded: bool


def normalize_column_map(
    columns: Container[Hashable],
    output: Literal['input', 'model'],
    column_map: Mapping[Hashable, Hashable] | None,
) -> dict[Hashable, Hashable]:
    if output not in ('input', 'model'):
        raise ValueError('output must be input or model')
    explicit = dict(column_map) if column_map is not None else {}
    if explicit and output == 'model':
        raise ValueError('column_map requires input-aligned output')
    if any(column not in columns for column in explicit):
        raise ValidationError('column_map contains an unknown input column')
    if len(set(explicit.values())) != len(explicit):
        raise ValidationError('column_map must map to distinct output keys')
    return explicit


class RecordProjection:
    """Reuse field and column mappings across the rows of a validation call."""

    def __init__(
        self,
        fields: list[FieldProjection],
        computed_keys: tuple[str, ...],
        explicit: dict[Hashable, Hashable],
        output: Literal['input', 'model'],
    ) -> None:
        self._fields = fields
        self._explicit = explicit
        self._output = output
        self._known_inputs: set[Hashable] = set()
        for field in fields:
            self._known_inputs.update(field.output_keys)
            self._known_inputs.update(path[0] for path in field.input_paths)
        self._preferred_keys = Counter(
            field.output_keys[0] for field in fields if not field.excluded
        )
        computed_counts = Counter(computed_keys)
        self._computed_collisions = {
            key
            for key, count in computed_counts.items()
            if count > 1 or key in self._preferred_keys
        }
        self._serialized_keys = self._preferred_keys.keys() | computed_counts.keys()
        self.conditional_keys = {
            field.output_keys[0]
            for field in fields
            if field.conditionally_excluded and not field.excluded
        }
        self.reserved_keys = self._known_inputs | set(computed_keys)

    def project(
        self,
        record: dict[Any, Any],
        dumped: Mapping[Hashable, Any],
        extra_keys: set[Hashable],
        extra_aliases: Mapping[str, str],
    ) -> dict[Any, Any]:
        separate_keys: set[Hashable] = set()
        if extra_aliases:
            dumped, separate_keys = _restore_extra_keys(dumped, extra_aliases)
            extra_keys = {
                extra_aliases.get(key, key) if isinstance(key, str) else key for key in extra_keys
            }

        model_keys = dumped.keys() - separate_keys if separate_keys else dumped.keys()
        computed_collisions = self._computed_collisions & model_keys
        if computed_collisions:
            keys = ', '.join(sorted(map(repr, computed_collisions)))
            raise ValidationError(f'Computed fields share serialized keys {keys}')
        collisions = extra_keys & self._serialized_keys & model_keys
        if collisions:
            keys = ', '.join(sorted(map(repr, collisions)))
            raise ValidationError(f'Serialized field keys collide with allowed extras {keys}')
        if self._output == 'model':
            return dict(dumped)

        explicit = self._explicit
        projected: dict[Any, Any] = {}
        used_keys = set(explicit.values())
        for column, key in explicit.items():
            if key not in dumped:
                raise ValidationError(
                    f'Output key {key!r} for column {column!r} was not serialized'
                )
            projected[column] = dumped[key]

        for field in self._fields:
            path = _matching_path(record, field.input_paths)
            if (
                path is None
                or field.excluded
                or path[0] in explicit
                or field.output_keys[0] in separate_keys
            ):
                continue
            column = path[0]
            key = next(
                (
                    candidate
                    for offset, candidate in enumerate(field.output_keys)
                    if candidate in dumped
                    and self._preferred_keys[candidate] == (1 if offset == 0 else 0)
                ),
                None,
            )
            if key is None and field.conditionally_excluded and field.output_keys[0] not in dumped:
                continue
            if (
                len(path) != 1
                or key is None
                or column in projected
                or key in used_keys
                or key in extra_keys
            ):
                raise ValidationError(
                    f'Cannot map validated field {field.name!r} to input column {column!r}. '
                    "Use column_map to specify its output key or use output='model'."
                )
            projected[column] = dumped[key]
            used_keys.add(key)

        for column in record.keys() & dumped.keys():
            if (
                (column in extra_keys or column not in self._known_inputs)
                and column not in used_keys
                and column not in explicit
            ):
                projected[column] = dumped[column]
        return projected


def _restore_extra_keys(
    dumped: Mapping[Hashable, Any], extra_aliases: Mapping[str, str]
) -> tuple[dict[Hashable, Any], set[Hashable]]:
    restored: dict[Hashable, Any] = {}
    separate_keys: set[Hashable] = set()
    for key, value in dumped.items():
        if isinstance(key, str) and key in extra_aliases:
            original = extra_aliases[key]
            if original in dumped:
                raise ValidationError(
                    f'Serialized field keys collide with allowed extras {original!r}'
                )
            separate_keys.add(original)
            key = original
        restored[key] = value
    return restored, separate_keys


def _matching_path(
    record: dict[Any, Any], paths: list[tuple[str | int, ...]]
) -> tuple[str | int, ...] | None:
    for path in paths:
        value: Any = record
        try:
            for part in path:
                if isinstance(value, str):
                    break
                value = value[part]
            else:
                return path
        except (KeyError, IndexError, TypeError):
            continue
    return None
