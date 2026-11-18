"""Tests for abraxos.validate module."""

import pandas as pd
import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_serializer,
    model_validator,
)

from abraxos import ValidationError
from abraxos.validate import ValidateResult, validate


class TestOutputSchemas:
    @pytest.mark.parametrize('use_instance', [False, True])
    def test_pydantic_input_alias_keeps_the_validated_value(self, use_instance):
        class Item(BaseModel):
            id: int = Field(alias='External ID')

        source = pd.DataFrame({'External ID': ['123']}, index=pd.Index(['a'], name='record'))
        model = Item.model_validate({'External ID': '0'}) if use_instance else Item
        result = validate(source, model)
        assert result.errors == []
        assert result.success_df.to_dict('records') == [{'External ID': 123}]
        pd.testing.assert_index_equal(result.success_df.index, source.index)

    def test_validation_and_serialization_aliases_with_defaults(self):
        class Item(BaseModel):
            model_config = ConfigDict(serialize_by_alias=True)
            id: int = Field(validation_alias='External ID', serialization_alias='stored_id')
            active: bool = True
            secret: str = Field(exclude=True)
            amount: int = Field(exclude_if=lambda value: value == 0)

        source = pd.DataFrame(
            {'External ID': ['123'], 'amount': [0], 'secret': ['hidden']},
            index=['source-key'],
        )
        projected = validate(source, Item)
        assert projected.success_df['External ID'].tolist() == [123]
        assert projected.success_df[['amount', 'secret']].isna().all().all()
        serialized = validate(source, Item, output='model')
        assert serialized.success_df.to_dict('records') == [{'stored_id': 123, 'active': True}]
        assert serialized.success_df.index.tolist() == ['source-key']

    @pytest.mark.parametrize('output', ['input', 'model'])
    def test_extra_cannot_overwrite_a_serialized_field(self, output):
        class Item(BaseModel):
            model_config = ConfigDict(extra='allow', serialize_by_alias=True)
            amount: int = Field(validation_alias='raw', serialization_alias='normalized')

        source = pd.DataFrame({'raw': ['12'], 'normalized': [999]})
        with pytest.raises(ValidationError, match="allowed extras 'normalized'"):
            validate(source, Item, output=output)

    @pytest.mark.parametrize('output', ['input', 'model'])
    def test_computed_field_cannot_overwrite_a_serialized_field(self, output):
        class Item(BaseModel):
            model_config = ConfigDict(serialize_by_alias=True)
            quantity: int = Field(serialization_alias='amount')

            @computed_field(alias='amount')
            @property
            def calculated(self) -> int:
                return 999

        with pytest.raises(ValidationError, match="Computed fields share serialized keys 'amount'"):
            validate(pd.DataFrame({'quantity': ['12']}), Item, output=output)

    @pytest.mark.parametrize('output', ['input', 'model'])
    def test_extra_key_is_available_when_the_field_is_excluded_for_the_row(self, output):
        checked = []

        def exclude_zero(value):
            checked.append(value)
            return value == 0

        class Item(BaseModel):
            model_config = ConfigDict(extra='allow', serialize_by_alias=True)
            quantity: int = Field(serialization_alias='amount', exclude_if=exclude_zero)

        source = pd.DataFrame({'quantity': ['0'], 'amount': [999], '_amount': [42]})
        result = validate(source, Item, output=output)
        assert result.errors == []
        assert result.success_df['amount'].tolist() == [999]
        assert result.success_df['_amount'].tolist() == [42]
        if output == 'input':
            assert result.success_df['quantity'].isna().all()
        else:
            assert result.success_df.columns.tolist() == ['amount', '_amount']

        with pytest.raises(ValidationError, match="allowed extras 'amount'"):
            validate(source.assign(quantity='12'), Item, output=output)
        assert checked == [0, 12]

    def test_allowed_extra_can_match_an_inactive_serialization_alias(self):
        class Item(BaseModel):
            model_config = ConfigDict(extra='allow')
            amount: int = Field(validation_alias='raw', serialization_alias='normalized')

        source = pd.DataFrame({'raw': ['12'], 'normalized': [999]})
        assert validate(source, Item).success_df.to_dict('records') == [
            {'raw': 12, 'normalized': 999}
        ]

    def test_custom_serializer_keeps_extras_under_the_original_names(self):
        class Item(BaseModel):
            model_config = ConfigDict(extra='allow', serialize_by_alias=True)
            quantity: int = Field(serialization_alias='amount', exclude_if=lambda value: value == 0)

            @model_serializer
            def serialize(self):
                return {'entered_amount': self.amount}

        source = pd.DataFrame({'quantity': [0], 'amount': [999]})
        result = validate(source, Item, output='model')
        assert result.errors == []
        assert result.success_df.to_dict('records') == [{'entered_amount': 999}]

    def test_alias_generator_and_name_fallback(self):
        class Item(BaseModel):
            model_config = ConfigDict(alias_generator=str.upper, validate_by_name=True)
            identifier: int

        assert validate(pd.DataFrame({'IDENTIFIER': ['5']}), Item).success_df.iloc[0, 0] == 5
        assert validate(pd.DataFrame({'identifier': ['6']}), Item).success_df.iloc[0, 0] == 6

    def test_model_defaults_do_not_populate_ignored_input_aliases(self):
        class Item(BaseModel):
            identifier: int = Field(default=7, alias='ID')

        source = pd.DataFrame({'identifier': ['123']})
        assert validate(source, Item).success_df['identifier'].isna().all()
        assert validate(source, Item, output='model').success_df['identifier'].tolist() == [7]

    def test_before_validator_can_normalize_keys_without_losing_the_input_label(self):
        class Item(BaseModel):
            model_config = ConfigDict(validate_by_name=True)
            identifier: int = Field(alias='ID')

            @model_validator(mode='before')
            @classmethod
            def normalize(cls, record):
                record['identifier'] = record.pop('ID')
                return record

        result = validate(pd.DataFrame({'ID': ['9']}), Item)
        assert result.success_df['ID'].tolist() == [9]

    def test_alias_choices_support_flat_keys_and_require_explicit_nested_projection(self):
        class Item(BaseModel):
            identifier: int = Field(validation_alias=AliasChoices('ID', AliasPath('wrapped', 0)))

        assert validate(pd.DataFrame({'ID': ['9']}), Item).success_df.iloc[0, 0] == 9
        source = pd.DataFrame({'wrapped': [['10']]})
        with pytest.raises(ValidationError, match='Cannot map validated field'):
            validate(source, Item)
        result = validate(source, Item, column_map={'wrapped': 'identifier'})
        assert result.success_df.to_dict('records') == [{'wrapped': 10}]

    def test_validation_alias_shared_by_two_fields_requires_an_explicit_projection(self):
        class Item(BaseModel):
            number: int = Field(alias='ID')
            text: str = Field(alias='ID')

        source = pd.DataFrame({'ID': ['123']})
        with pytest.raises(ValidationError, match='Cannot map validated field'):
            validate(source, Item)
        assert validate(source, Item, column_map={'ID': 'number'}).success_df.iloc[0, 0] == 123

    def test_custom_serializers_require_explicit_mapping_for_renamed_fields(self):
        class Item(BaseModel):
            id: int

            @model_serializer
            def serialize(self):
                return {'renamed': self.id}

        source = pd.DataFrame({'id': ['123']})
        with pytest.raises(ValidationError, match='Cannot map validated field'):
            validate(source, Item)
        result = validate(source, Item, column_map={'id': 'renamed'})
        assert result.success_df.to_dict('records') == [{'id': 123}]
        with pytest.raises(ValidationError, match='was not serialized'):
            validate(source, Item, column_map={'id': 'missing'})

    def test_custom_models_can_map_serialized_keys(self):
        class Item:
            def model_validate(self, record):
                self.value = int(record['External ID'])
                return self

            def model_dump(self):
                return {'id': self.value}

        result = validate(
            pd.DataFrame({'External ID': ['123']}), Item(), column_map={'External ID': 'id'}
        )
        assert result.success_df.to_dict('records') == [{'External ID': 123}]

    def test_duplicate_labels_are_rejected_before_validation(self):
        class Item:
            def model_validate(self, record):
                pytest.fail('duplicate labels must be rejected before validation')

        source = pd.DataFrame([['invalid', '123']], columns=['id', 'id'])
        with pytest.raises(ValueError, match='labels must be unique'):
            validate(source, Item())

    @pytest.mark.parametrize('output', ['input', 'model'])
    def test_non_mapping_dump_raises_instead_of_returning_a_row_error(self, output):
        class Item:
            def model_validate(self, record):
                return self

            def model_dump(self):
                return [1]

        with pytest.raises(ValidationError, match='model_dump must return a mapping'):
            validate(pd.DataFrame({'id': [1]}), Item(), output=output)


class TestValidateResult:
    """Tests for ValidateResult named tuple."""

    def test_named_tuple_fields(self):
        """Test that ValidateResult has correct fields."""
        df = pd.DataFrame({'a': [1, 2]})
        result = ValidateResult(errors=[], errored_df=df.iloc[:0], success_df=df)

        assert result.errors == []
        assert result.errored_df.empty
        assert result.success_df.equals(df)

    def test_preserves_index_and_original_failures_when_model_omits_fields(self):
        class Item(BaseModel):
            amount: int

        df = pd.DataFrame(
            {'amount': ['10', 'invalid', '30'], 'ignored': pd.array([1, None, 3], dtype='Int64')},
            index=pd.MultiIndex.from_tuples(
                [('A', 1), ('A', 1), ('B', 1)], names=['category', 'item']
            ),
        )

        result = validate(df, Item)

        assert len(result.errors) == 1
        pd.testing.assert_frame_equal(result.errored_df, df.iloc[[1]])
        pd.testing.assert_index_equal(result.success_df.index, df.index[[0, 2]])
        assert result.success_df.columns.tolist() == ['amount', 'ignored']
        assert result.success_df['amount'].tolist() == [10, 30]
        assert result.success_df['ignored'].isna().all()

    def test_mutating_validator_preserves_source_and_rejected_values(self):
        class Item(BaseModel):
            payload: list[int]

            @field_validator('payload', mode='before')
            @classmethod
            def strip_marker(cls, value):
                if value.pop(0) == 'reject':
                    raise ValueError('Rejected item')
                return value

        source = pd.DataFrame({'payload': [['accept', 1], ['reject', 2]]}, index=['kept', 'failed'])
        result = validate(source, Item)

        assert len(result.errors) == 1
        assert source['payload'].tolist() == [['accept', 1], ['reject', 2]]
        assert result.success_df.loc['kept', 'payload'] == [1]
        assert result.errored_df.loc['failed', 'payload'] == ['reject', 2]


class TestValidateSuccess:
    """Tests for successful validation."""

    def test_all_valid_rows(self):
        """Test validation where all rows are valid."""

        class SimpleModel:
            def model_validate(self, record):
                if record['age'] < 0:
                    raise ValueError('Age must be positive')
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]})
        result = validate(df, SimpleModel())

        assert result.errors == []
        assert result.errored_df.empty
        assert len(result.success_df) == 2

    def test_single_row_validation(self):
        """Test validating single-row DataFrame."""

        class SimpleModel:
            def model_validate(self, record):
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice'], 'age': [25]})
        result = validate(df, SimpleModel())

        assert result.errors == []
        assert len(result.success_df) == 1

    def test_empty_dataframe(self):
        """Test validating empty DataFrame."""

        class SimpleModel:
            def model_validate(self, record):
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': [], 'age': []})
        result = validate(df, SimpleModel())

        assert result.errors == []
        assert result.success_df.empty
        assert result.errored_df.empty


class TestValidateFailure:
    """Tests for validation failures."""

    def test_all_invalid_rows(self):
        """Test validation where all rows fail."""

        class StrictModel:
            def model_validate(self, record):
                raise ValueError('Always fails')

            def model_dump(self):
                return {}

        df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]})
        result = validate(df, StrictModel())

        assert len(result.errors) == 2
        assert len(result.errored_df) == 2
        assert result.success_df.empty

    def test_single_row_failure(self):
        """Test failure on single row."""

        class StrictModel:
            def model_validate(self, record):
                raise ValueError('Validation failed')

            def model_dump(self):
                return {}

        df = pd.DataFrame({'name': ['Alice'], 'age': [25]})
        result = validate(df, StrictModel())

        assert len(result.errors) == 1
        assert len(result.errored_df) == 1
        assert result.success_df.empty


class TestValidatePartialFailure:
    """Tests for partial validation failures."""

    def test_mixed_validation_results(self):
        """Test validation with some successes and some failures."""

        class AgeValidator:
            def model_validate(self, record):
                if record['age'] < 30:
                    raise ValueError('Too young')
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice', 'Bob', 'Charlie'], 'age': [25, 35, 28]})
        result = validate(df, AgeValidator())

        assert len(result.errors) == 2  # Alice and Charlie fail
        assert len(result.errored_df) == 2
        assert len(result.success_df) == 1  # Only Bob succeeds
        assert result.success_df['name'].iloc[0] == 'Bob'

    def test_preserves_failed_row_data(self):
        """Test that failed rows preserve original data."""

        class FailOnBob:
            def model_validate(self, record):
                if record['name'] == 'Bob':
                    raise ValueError('Bob not allowed')
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]})
        result = validate(df, FailOnBob())

        # Check that Bob's row is in errored_df with original data
        assert len(result.errored_df) == 1
        assert result.errored_df['name'].iloc[0] == 'Bob'
        assert result.errored_df['age'].iloc[0] == 30


class TestValidateWithTransformation:
    """Tests for validation that transforms data."""

    def test_model_transforms_data(self):
        """Test that validation can transform the data."""

        class TransformingModel:
            def model_validate(self, record):
                self._record = {'name': record['name'].upper(), 'age': record['age'] * 2}
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['alice', 'bob'], 'age': [25, 30]})
        result = validate(df, TransformingModel())

        assert result.errors == []
        assert result.success_df['name'].iloc[0] == 'ALICE'
        assert result.success_df['age'].iloc[0] == 50

    def test_model_adds_fields(self):
        """Test validation that adds new fields."""

        class AddFieldsModel:
            def model_validate(self, record):
                self._record = {
                    'name': record['name'],
                    'age': record['age'],
                    'doubled_age': record['age'] * 2,
                }
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice'], 'age': [25]})
        result = validate(df, AddFieldsModel())

        # Note: validate preserves original column structure
        # Additional fields from model_dump are included
        assert result.errors == []


class TestValidateColumnOrder:
    """Tests for column order preservation."""

    def test_preserves_column_order(self):
        """Test that column order is preserved from input."""

        class SimpleModel:
            def model_validate(self, record):
                # Return fields in different order
                self._record = {'age': record['age'], 'name': record['name']}
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice'], 'age': [25]})
        result = validate(df, SimpleModel())

        # Should preserve original column order
        assert list(result.success_df.columns) == ['name', 'age']

    def test_errored_df_column_order(self):
        """Test that errored_df preserves column order."""

        class FailingModel:
            def model_validate(self, record):
                raise ValueError('Failed')

            def model_dump(self):
                return {}

        df = pd.DataFrame({'name': ['Alice'], 'age': [25], 'city': ['NYC']})
        result = validate(df, FailingModel())

        assert list(result.errored_df.columns) == list(df.columns)


class TestValidateWithNaN:
    """Tests for validation with NaN/None values."""

    def test_handles_nan_values(self):
        """Test validation with NaN values."""
        import numpy as np

        class NanAwareModel:
            def model_validate(self, record):
                if record['age'] is None:
                    raise ValueError('Age is required')
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, np.nan]})
        result = validate(df, NanAwareModel())

        # Bob should fail due to NaN age
        assert len(result.errors) == 1
        assert len(result.success_df) == 1
        assert len(result.errored_df) == 1


class TestValidateWithIndex:
    """Tests for index preservation."""

    def test_preserves_index(self):
        """Test that DataFrame index is preserved."""

        class SimpleModel:
            def model_validate(self, record):
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]}, index=[100, 200])
        result = validate(df, SimpleModel())

        assert list(result.success_df.index) == [100, 200]

    def test_preserves_index_on_failure(self):
        """Test that index is preserved in errored_df."""

        class FailingModel:
            def model_validate(self, record):
                raise ValueError('Failed')

            def model_dump(self):
                return {}

        df = pd.DataFrame({'name': ['Alice'], 'age': [25]}, index=[999])
        result = validate(df, FailingModel())

        assert result.errored_df.index[0] == 999


class TestValidateErrorDetails:
    """Tests for error information."""

    def test_errors_are_exceptions(self):
        """Test that errors list contains Exception objects."""

        class CustomErrorModel:
            def model_validate(self, record):
                raise ValueError('Custom error message')

            def model_dump(self):
                return {}

        df = pd.DataFrame({'name': ['Alice'], 'age': [25]})
        result = validate(df, CustomErrorModel())

        assert len(result.errors) == 1
        assert isinstance(result.errors[0], Exception)
        assert 'Custom error message' in str(result.errors[0])

    def test_different_error_types(self):
        """Test that different exception types are captured."""

        class MultiErrorModel:
            def __init__(self):
                self.call_count = 0

            def model_validate(self, record):
                self.call_count += 1
                if self.call_count == 1:
                    raise ValueError('ValueError')
                else:
                    raise TypeError('TypeError')

            def model_dump(self):
                return {}

        df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]})
        model = MultiErrorModel()
        result = validate(df, model)

        assert len(result.errors) == 2
        assert any(isinstance(e, ValueError) for e in result.errors)
        assert any(isinstance(e, TypeError) for e in result.errors)

    @pytest.mark.parametrize('output', ['input', 'model'])
    def test_validates_and_dumps_once_per_row_and_keeps_failures_in_input_order(self, output):
        validation_error = ValueError('Invalid input')
        serialization_error = RuntimeError('Cannot serialize row')
        calls = []

        class Item:
            def model_validate(self, record):
                self.value = record['value']
                calls.append(('validate', self.value))
                if self.value == 'invalid':
                    raise validation_error
                return self

            def model_dump(self):
                calls.append(('dump', self.value))
                if self.value == 'unserializable':
                    raise serialization_error
                return {'value': int(self.value)}

        source = pd.DataFrame(
            {'value': ['1', 'invalid', 'unserializable', '2']}, index=['a', 'b', 'a', 'b']
        )
        result = validate(source, Item(), output=output)

        assert calls == [
            ('validate', '1'),
            ('dump', '1'),
            ('validate', 'invalid'),
            ('validate', 'unserializable'),
            ('dump', 'unserializable'),
            ('validate', '2'),
            ('dump', '2'),
        ]
        assert result.errors == [validation_error, serialization_error]
        pd.testing.assert_frame_equal(result.errored_df, source.iloc[[1, 2]])
        pd.testing.assert_frame_equal(
            result.success_df, pd.DataFrame({'value': [1, 2]}, index=['a', 'b'])
        )


class TestValidateWithModelClass:
    """Tests for using model class vs instance."""

    def test_accepts_model_instance(self):
        """Test that validate accepts model instance."""

        class Model:
            def model_validate(self, record):
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice'], 'age': [25]})
        result = validate(df, Model())

        assert result.errors == []

    def test_accepts_model_class(self):
        """Test that validate can accept model class (for Pydantic compatibility)."""

        class Model:
            def model_validate(self, record):
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['Alice'], 'age': [25]})
        # Should work with class too
        result = validate(df, Model())

        assert result.errors == []


class TestIntegration:
    """Integration tests for validate module."""

    def test_validate_after_transform(self):
        """Test validation after transformation."""
        from abraxos.transform import transform

        class UppercaseModel:
            def model_validate(self, record):
                self._record = record
                return self

            def model_dump(self):
                return self._record

        df = pd.DataFrame({'name': ['alice', 'bob'], 'age': [25, 30]})

        # First transform
        def uppercase(df):
            df = df.copy()
            df['name'] = df['name'].str.upper()
            return df

        transform_result = transform(df, uppercase)

        # Then validate
        validate_result = validate(transform_result.success_df, UppercaseModel())

        assert validate_result.errors == []
        assert all(transform_result.success_df['name'].str.isupper())
