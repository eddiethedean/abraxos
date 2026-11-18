"""Pydantic model validation for DataFrame rows."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from copy import deepcopy
from typing import Any, Literal, NamedTuple, Protocol

import pandas as pd

from ._pydantic_schema import pydantic_extra_keys, pydantic_fields, separate_conditional_extras
from ._validation_projection import RecordProjection, normalize_column_map
from .exceptions import ValidationError
from .utils import clear, to_records

__all__ = ['PydanticModel', 'ValidateResult', 'validate']


class _ValidatedModel(Protocol):
    def model_dump(self) -> dict[Any, Any]: ...


class PydanticModel(Protocol):
    """
    Protocol representing a Pydantic-like model for validation and serialization.
    """

    def model_validate(self, record: dict[Any, Any], /) -> _ValidatedModel:
        """
        Validates a dictionary record and returns a validated model instance.
        """
        ...


class ValidateResult(NamedTuple):
    """
    Result of validating a DataFrame using a Pydantic-like model.

    Attributes
    ----------
    errors : list of Exception
        List of exceptions encountered during validation.
    errored_df : pd.DataFrame
        DataFrame of rows that failed validation.
    success_df : pd.DataFrame
        DataFrame of successfully validated and serialized rows.
    """

    errors: list[Exception]
    errored_df: pd.DataFrame
    success_df: pd.DataFrame


def validate(
    df: pd.DataFrame,
    model: PydanticModel,
    *,
    output: Literal['input', 'model'] = 'input',
    column_map: Mapping[Hashable, Hashable] | None = None,
) -> ValidateResult:
    """
    Validates each row in a DataFrame using a Pydantic-like model.

    A copy of each record, including its mutable values, is passed to the
    model's `model_validate` method.
    Input-aligned output maps validated fields back to their original columns.
    Deliberately excluded or ignored columns receive missing values. Use
    model-shaped output to keep the complete serialized row, including defaults.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing records to be validated.
    model : PydanticModel
        A Pydantic model class or an object that exposes a compatible
        `model_validate` method.
    output : {'input', 'model'}, optional
        Select the input-aligned or serialized model schema. Both preserve
        original row indexes.
    column_map : mapping, optional
        Map input column labels to serialized keys when using input-aligned
        output. For example, use `{'External ID': 'id'}` for a custom model.

    Returns
    -------
    ValidateResult
        A named tuple with:
        - errors: List of exceptions raised during validation.
        - errored_df: DataFrame of rows that failed validation.
        - success_df: DataFrame of rows that were successfully validated.

    Raises
    ------
    ValidationError
        Serialized keys collide or the serialized output cannot be mapped to
        the requested columns.

    Examples
    --------
    >>> import pandas as pd
    >>> from pydantic import BaseModel
    >>> from abraxos import validate
    >>> class Person(BaseModel):
    ...     name: str
    ...     age: int
    >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 'invalid']})
    >>> result = validate(df, Person)
    >>> len(result.success_df)
    1
    >>> len(result.errored_df)
    1
    """
    explicit = normalize_column_map(df.columns, output, column_map)
    records = to_records(df)
    if not callable(getattr(model, 'model_validate', None)):
        raise TypeError('model must provide a callable model_validate method')
    fields, computed_keys = pydantic_fields(model)
    projection = RecordProjection(fields, computed_keys, explicit, output)
    errors: list[Exception] = []
    failed_positions: list[int] = []
    valid_positions: list[int] = []
    valid_records: list[dict[Any, Any]] = []

    for position, record in enumerate(records):
        try:
            memo: dict[int, Any] = {}
            validated = model.model_validate(
                {column: deepcopy(value, memo) for column, value in record.items()}
            )
            dump_model, extra_aliases = separate_conditional_extras(
                validated, projection.conditional_keys, projection.reserved_keys
            )
            dumped = dump_model.model_dump()
        except Exception as error:
            errors.append(error)
            failed_positions.append(position)
        else:
            if not isinstance(dumped, Mapping):
                raise ValidationError('model_dump must return a mapping of field names to values')
            extra_keys = pydantic_extra_keys(dump_model) if fields or computed_keys else set()
            valid_records.append(projection.project(record, dumped, extra_keys, extra_aliases))
            valid_positions.append(position)

    errored_df = df.iloc[failed_positions] if failed_positions else clear(df)
    success_df = clear(df)
    if valid_records or output == 'model':
        index = df.index.take(valid_positions) if failed_positions else df.index
        columns = df.columns if output == 'input' else None
        success_df = pd.DataFrame(valid_records, columns=columns, index=index)

    return ValidateResult(errors, errored_df, success_df)
