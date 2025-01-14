import typing as t

import pandas as pd
import pydantic


class ValidateResult(t.NamedTuple):
    errors: list[pydantic.ValidationError]
    errored_df: pd.DataFrame
    success_df: pd.DataFrame


def validate(
    df: pd.DataFrame,
    model: pydantic.BaseModel
) -> ValidateResult:
    errors: list[pydantic.ValidationError] = []
    errored_df = df.astype('object')
    valid_df = df.astype('object')

    for i, row in df.iterrows():
        record = row.to_dict()
        try:
            valid = model.model_validate(record)
        except pydantic.ValidationError as e:
            errors.append(e)
            valid_df.drop(i, inplace=True)
        else:
            valid_df.loc[i] = valid.model_dump()
            errored_df.drop(i, inplace=True)

    errored_df = errored_df.infer_objects()
    valid_df = valid_df.infer_objects()
    return ValidateResult(errors, errored_df, valid_df)