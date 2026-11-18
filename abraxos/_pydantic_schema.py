"""Translate optional Pydantic model metadata into projection rules."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import TypeVar

from ._validation_projection import FieldProjection

_Model = TypeVar('_Model')


def pydantic_fields(model: object) -> tuple[list[FieldProjection], tuple[str, ...]]:
    try:
        from pydantic import AliasChoices, AliasPath, BaseModel
    except ModuleNotFoundError as error:
        if error.name != 'pydantic':
            raise
        return [], ()

    cls: type[object] = model if isinstance(model, type) else type(model)
    if not issubclass(cls, BaseModel):
        return [], ()

    config = cls.model_config
    by_alias = config.get('validate_by_alias', True)
    by_name = config.get('validate_by_name', config.get('populate_by_name', not by_alias))
    serialize_by_alias = config.get('serialize_by_alias', False)
    fields = []
    for name, field in cls.model_fields.items():
        paths: list[tuple[str | int, ...]] = []
        alias = field.validation_alias
        if by_alias and alias is not None:
            if isinstance(alias, AliasChoices):
                paths.extend(tuple(choice) for choice in alias.convert_to_aliases())
            elif isinstance(alias, AliasPath):
                paths.append(tuple(alias.path))
            else:
                paths.append((alias,))
        if by_name or alias is None:
            paths.append((name,))

        keys: tuple[str, ...]
        serialized = field.serialization_alias
        if serialized is not None and serialized != name:
            keys = (serialized, name) if serialize_by_alias else (name, serialized)
        else:
            keys = (name,)
        fields.append(
            FieldProjection(name, paths, keys, field.exclude is True, field.exclude_if is not None)
        )
    computed_keys = tuple(
        field.alias if serialize_by_alias and field.alias is not None else name
        for name, field in cls.model_computed_fields.items()
    )
    return fields, computed_keys


def pydantic_extra_keys(validated: object) -> set[Hashable]:
    extras = getattr(validated, 'model_extra', None)
    return set(extras) if isinstance(extras, Mapping) else set()


def separate_conditional_extras(
    validated: _Model, conditional_keys: set[str], reserved_keys: set[Hashable]
) -> tuple[_Model, dict[str, str]]:
    """Give overlapping extras distinct keys for a single serialization pass."""
    if not conditional_keys:
        return validated, {}
    extras = getattr(validated, 'model_extra', None)
    if not isinstance(extras, dict) or not (overlaps := conditional_keys & extras.keys()):
        return validated, {}

    from pydantic import BaseModel

    if not isinstance(validated, BaseModel):
        return validated, {}
    cls = type(validated)
    if cls.model_dump is not BaseModel.model_dump or cls.__pydantic_decorators__.model_serializers:
        # A custom serializer may read or rename extras by their original keys.
        return validated, {}

    occupied = reserved_keys | extras.keys()
    replacements: dict[str, str] = {}
    for key in sorted(overlaps):
        alternate = f'_{key}'
        while alternate in occupied:
            alternate = f'_{alternate}'
        occupied.add(alternate)
        replacements[key] = alternate

    # model_copy() keeps the validated values and gives the extras their own mapping.
    separate = validated.model_copy()
    separate_extras = separate.model_extra
    assert separate_extras is not None
    rekeyed = {replacements.get(key, key): value for key, value in separate_extras.items()}
    separate_extras.clear()
    separate_extras.update(rekeyed)
    return separate, {alternate: key for key, alternate in replacements.items()}
