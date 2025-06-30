import typing as t
import abc

import pandas as pd

from abraxos import utils


class PydanticModel(t.Protocol):
    """
    Protocol representing a Pydantic-like model for validation and serialization.
    """

    @abc.abstractmethod
    def model_validate(self, record: dict) -> 'PydanticModel':
        """
        Validates a dictionary record and returns a validated model instance.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def model_dump(self) -> dict:
        """
        Serializes the model into a dictionary.
        """
        raise NotImplementedError


class ValidateResult(t.NamedTuple):
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
    errors: t.List[Exception]
    errored_df: pd.DataFrame
    success_df: pd.DataFrame


def validate(
    df: pd.DataFrame,
    model: PydanticModel
) -> ValidateResult:
    """
    Validates each row in a DataFrame using a Pydantic-like model.

    Each record is passed to the model's `model_validate` method.
    Successfully validated models are converted back into rows using `model_dump`.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing records to be validated.
    model : PydanticModel
        A Pydantic-style model instance with `model_validate` and `model_dump` methods.

    Returns
    -------
    ValidateResult
        A named tuple with:
        - errors: List of exceptions raised during validation.
        - errored_df: DataFrame of rows that failed validation.
        - success_df: DataFrame of rows that were successfully validated.

    Examples
    --------
    >>> import pandas as pd
    >>> class SampleModel:
    ...     def model_validate(self, record: dict):
    ...         if isinstance(record.get("value"), int):
    ...             self._val = record["value"] * 2
    ...             return self
    ...         raise ValueError("Invalid value")
    ...     def model_dump(self):
    ...         return {"value": self._val}
    >>> df = pd.DataFrame({'value': [1, 'a', 3]})
    >>> validate(df, SampleModel())
    ValidateResult(
        errors=[ValueError('Invalid value')],
        errored_df=   value
    1     a,
        success_df=   value
    0      2
    2      6)
    """
    errors: t.List[Exception] = []
    errored_records: t.List[pd.Series] = []
    valid_records: t.List[pd.Series] = []

    records: t.List[dict] = utils.to_records(df)

    for index, record in zip(df.index, records):
        try:
            validated: PydanticModel = model.model_validate(record)
            valid_records.append(pd.Series(validated.model_dump(), name=index))
        except Exception as e:
            errors.append(e)
            errored_records.append(pd.Series(record, name=index))

    return ValidateResult(
        errors,
        pd.DataFrame(errored_records, columns=df.columns),
        pd.DataFrame(valid_records, columns=df.columns)
    )
