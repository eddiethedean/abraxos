import typing as t
import abc

import pandas as pd


class PydanticModel(t.Protocol):
    @abc.abstractmethod
    def model_validate(self, record: dict) -> t.Self:
        raise NotImplementedError
    
    @abc.abstractmethod
    def model_dump(self) -> dict:
        raise NotImplementedError


class ValidateResult(t.NamedTuple):
    errors: list[Exception]
    errored_df: pd.DataFrame
    success_df: pd.DataFrame


def validate(
    df: pd.DataFrame,
    model: PydanticModel
) -> ValidateResult:
    """
    Validates each row in a DataFrame using a Pydantic model and categorizes them into valid and errored records.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing records to be validated.
    model : PydanticModel
        A Pydantic model with `model_validate` and `model_dump` methods for validation and serialization.

    Returns
    -------
    ValidateResult
        A named tuple containing:
        - errors: A list of exceptions encountered during validation.
        - errored_df: A DataFrame containing rows that failed validation.
        - success_df: A DataFrame containing successfully validated rows.

    Examples
    --------
    >>> import pandas as pd
    >>> class SampleModel:
    ...     def model_validate(self, record: dict):
    ...         if "value" in record and isinstance(record["value"], int):
    ...             return self
    ...         raise ValueError("Invalid record")
    ...     def model_dump(self):
    ...         return {"value": 42}
    >>> df = pd.DataFrame({'value': [1, 'a', 3]})
    >>> validate(df, SampleModel())
    ValidateResult(errors=[ValueError('Invalid record')], errored_df=value
    1     a, success_df=value
    0    42
    2    42)
    """
    errors: list[Exception] = []
    errored_records: list[pd.Series] = []
    valid_records: list[pd.Series] = []
    
    for _, row in df.iterrows():
        record: dict[str, t.Any] = row.to_dict()
        try:
            valid: PydanticModel = model.model_validate(record)
            valid_records.append(pd.Series(valid.model_dump(), index=df.columns))
        except Exception as e:
            errors.append(e)
            errored_records.append(row)

    return ValidateResult(
        errors,
        pd.DataFrame(errored_records, columns=df.columns),
        pd.DataFrame(valid_records, columns=df.columns)
    )