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
    errors: list[Exception] = []
    errored_df = df.astype('object')
    valid_df = df.astype('object')
    for i, row in df.iterrows():
        record = row.to_dict()
        try:
            valid = model.model_validate(record)
        except Exception as e:
            errors.append(e)
            valid_df.drop(i, inplace=True)
        else:
            valid_df.loc[i] = valid.model_dump()
            errored_df.drop(i, inplace=True)

    errored_df = errored_df.infer_objects()
    valid_df = valid_df.infer_objects()
    return ValidateResult(errors, errored_df, valid_df)