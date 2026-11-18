"""Tests for abraxos.extract module."""

import gzip
from io import BytesIO, StringIO

import pandas as pd
import pytest

from abraxos import CsvParseError
from abraxos.extract import ReadCsvResult, read_csv, read_csv_all, read_csv_chunks


class TestRecordRecovery:
    def test_full_and_chunked_reads_agree_on_width_and_multiline_fields(self):
        content = 'id,name\nEXTRA,1,Alice\n2,Bob\n3\n4,"Carol,\nDee"\n5,Emma,EXTRA\n'
        options = {'dtype': {'id': 'Int64', 'name': 'string'}}

        with StringIO(content) as complete_source, StringIO(content) as chunk_source:
            complete = read_csv(complete_source, **options)
            chunks = list(read_csv(chunk_source, chunksize=1, **options))
            assert not complete_source.closed
            assert not chunk_source.closed

        assert complete.bad_lines == [['EXTRA', '1', 'Alice'], ['3'], ['5', 'Emma', 'EXTRA']]
        assert [line for result in chunks for line in result.bad_lines] == complete.bad_lines
        assert [len(result.dataframe) for result in chunks] == [0, 1, 0, 1, 0]
        pd.testing.assert_frame_equal(
            pd.concat([result.dataframe for result in chunks]), complete.dataframe
        )
        assert complete.dataframe['id'].tolist() == [2, 4]
        assert complete.dataframe['name'].tolist() == ['Bob', 'Carol,\nDee']

    def test_width_is_checked_before_index_and_column_projection(self):
        data = StringIO('id,name,city\n1,TOO,MANY,COLUMNS\n2,Bob,NYC\n3,Carol,SF\n')
        result = read_csv(data, index_col='id', usecols=['id', 'name'])
        assert result.bad_lines == [['1', 'TOO', 'MANY', 'COLUMNS']]
        assert result.dataframe.index.tolist() == [2, 3]
        assert result.dataframe.to_dict('records') == [{'name': 'Bob'}, {'name': 'Carol'}]

    @pytest.mark.parametrize('malformed', ['2,"bad"tail\n3,Carol\n', '2,"unterminated\n3,Carol\n'])
    @pytest.mark.parametrize('chunksize', [None, 1])
    def test_bad_quoting_reports_start_of_logical_record(self, malformed, chunksize):
        source = StringIO('id,name\n1,"Alice\ncontinued"\n' + malformed)
        source.name = 'example.csv'
        with pytest.raises(CsvParseError, match='example.csv, line 4') as raised:
            result = read_csv(source, chunksize=chunksize)
            if chunksize is not None:
                list(result)
        assert raised.value.source == 'example.csv'
        assert raised.value.line == 4
        assert not source.closed

    def test_skiprows_comments_and_footer_apply_to_the_original_source(self):
        data = StringIO(
            '"ignored prologue\n'
            '# note\n'
            'id;name\n'
            '1;"value # in\n# quoted data"# inline note\n'
            '2;yes\n'
            'footer;with;extra;fields\n'
        )
        chunks = list(read_csv(data, sep=';', comment='#', skiprows={0}, skipfooter=1, chunksize=1))
        assert [result.bad_lines for result in chunks] == [[], []]
        assert [result.dataframe.iloc[0]['name'] for result in chunks] == [
            'value # in\n# quoted data',
            'yes',
        ]

    def test_explicit_names_declare_headerless_width_and_nrows_counts_accepted_rows(self):
        content = 'too,many,fields\n2,Bob\n3,"outside nrows\n'
        options = {'names': ['id', 'name'], 'nrows': 1}
        result = read_csv(StringIO(content), **options)
        assert result.bad_lines == [['too', 'many', 'fields']]
        assert result.dataframe.to_dict('records') == [{'id': 2, 'name': 'Bob'}]
        (chunk,) = read_csv(StringIO(content), chunksize=2, **options)
        assert chunk.bad_lines == result.bad_lines
        pd.testing.assert_frame_equal(chunk.dataframe, result.dataframe)
        empty = read_csv(StringIO('1,Alice\n'), header=None, nrows=0)
        assert empty.dataframe.columns.tolist() == [0, 1]

    def test_compressed_binary_source_with_bom_and_tab_dialect(self, tmp_path):
        path = tmp_path / 'records.tsv.gz'
        path.write_bytes(gzip.compress('\ufeff"id\tkey"\tname\n7\tAlice\n'.encode('utf-8')))
        result = read_csv(path, dialect='excel-tab')
        assert result.bad_lines == []
        assert result.dataframe.to_dict('records') == [{'id\tkey': 7, 'name': 'Alice'}]

    def test_explicit_compression_on_binary_stream(self):
        with BytesIO(gzip.compress(b'a,b\n1,Alice\n')) as source:
            result = read_csv(source, compression='gzip')
            assert result.dataframe.to_dict('records') == [{'a': 1, 'b': 'Alice'}]
            assert not source.closed

    def test_source_encoding_and_pandas_dtype_apply_at_their_respective_stages(self):
        content = 'id,city\n001,Zürich\n'.encode('latin-1')
        with BytesIO(content) as source:
            result = read_csv(source, encoding='latin-1', dtype={'id': 'string'})
            assert result.dataframe.to_dict('records') == [{'id': '001', 'city': 'Zürich'}]
            assert not source.closed

    def test_http_chunks_stream_and_close_the_response(self, monkeypatch):
        class Response(BytesIO):
            headers = {}

            def read(self, size=-1):
                assert size >= 0, 'the HTTP source must not be read in full'
                return super().read(size)

        response = Response(b'a,b\n1,Alice\n' + b'2,Bob\n' * 10_000)
        monkeypatch.setattr('abraxos._csv_source.urlopen', lambda request: response)
        chunks = read_csv('https://example.test/records.csv', chunksize=1)
        assert next(chunks).dataframe.to_dict('records') == [{'a': 1, 'b': 'Alice'}]
        assert response.tell() < len(response.getbuffer())
        chunks.close()
        assert response.closed

    @pytest.mark.parametrize('malformed', [False, True])
    def test_http_response_closes_on_exhaustion_or_parse_error(self, monkeypatch, malformed):
        class Response(BytesIO):
            headers = {}

        content = b'a,b\n1,Alice\n'
        if malformed:
            content += b'2,"unterminated\n'
        response = Response(content)
        monkeypatch.setattr('abraxos._csv_source.urlopen', lambda request: response)

        chunks = read_csv('https://example.test/records.csv', chunksize=1)
        assert next(chunks).dataframe.to_dict('records') == [{'a': 1, 'b': 'Alice'}]
        assert not response.closed
        if malformed:
            with pytest.raises(CsvParseError, match='records.csv, line 3'):
                next(chunks)
        else:
            with pytest.raises(StopIteration):
                next(chunks)
        assert response.closed

    def test_chunking_streams_nonseekable_input_and_leaves_caller_owned_stream_open(self):
        class NonSeekable(StringIO):
            def seek(self, *_):
                pytest.fail('chunked reading must not seek')

            def read(self, *_):
                pytest.fail('chunked reading must not buffer the whole input')

            def seekable(self):
                return False

        source = NonSeekable('a,b\n1,Alice\n2,Bob\n')
        with source:
            records = read_csv(source, chunksize=1)
            assert next(records).dataframe.to_dict('records') == [{'a': 1, 'b': 'Alice'}]
            records.close()
            assert not source.closed
            assert source.readline() == '2,Bob\n'

    @pytest.mark.parametrize(
        ('options', 'message'),
        [
            ({'engine': 'c'}, 'controls engine'),
            ({'on_bad_lines': 'skip'}, 'controls engine'),
            ({'sep': r'\s+'}, 'one-character separator'),
            ({'dialect': 'excel-tab', 'sep': ','}, 'conflicts'),
            ({'header': [0, 1]}, 'one header row'),
        ],
    )
    def test_unsupported_boundary_options_fail_explicitly(self, options, message):
        with pytest.raises(ValueError, match=message):
            read_csv(StringIO('a,b\n1,Alice\n'), **options)


class TestReadCsvResult:
    """Tests for ReadCsvResult named tuple."""

    def test_named_tuple_fields(self):
        """Test that ReadCsvResult has correct fields."""
        df = pd.DataFrame({'a': [1, 2]})
        result = ReadCsvResult(bad_lines=[], dataframe=df)

        assert result.bad_lines == []
        assert result.dataframe.equals(df)

    def test_named_tuple_access(self):
        """Test accessing fields by index and name."""
        df = pd.DataFrame({'a': [1, 2]})
        bad = [['x', 'y']]
        result = ReadCsvResult(bad, df)

        assert result[0] == bad
        assert result.bad_lines == bad
        assert result[1].equals(df)


class TestReadCsvAll:
    """Tests for read_csv_all function."""

    def test_read_valid_csv(self, valid_csv):
        """Test reading a valid CSV file."""
        result = read_csv_all(valid_csv)

        assert isinstance(result, ReadCsvResult)
        assert len(result.bad_lines) == 0
        assert len(result.dataframe) == 3
        assert list(result.dataframe.columns) == ['id', 'name', 'age']

    def test_read_csv_with_bad_lines(self, csv_with_bad_lines):
        """Test reading CSV with malformed lines."""
        result = read_csv_all(csv_with_bad_lines)

        assert isinstance(result, ReadCsvResult)
        assert len(result.bad_lines) > 0
        # Should have captured the malformed lines
        assert any(len(line) > 3 for line in result.bad_lines)
        # Valid data should still be parsed
        assert len(result.dataframe) > 0

    def test_read_empty_csv(self):
        """Test reading an empty CSV."""
        csv = StringIO('id,name,age\n')
        result = read_csv_all(csv)

        assert len(result.bad_lines) == 0
        assert result.dataframe.empty
        assert list(result.dataframe.columns) == ['id', 'name', 'age']

    def test_kwargs_passed_to_pandas(self):
        """Test that kwargs are passed to pandas.read_csv."""
        csv = StringIO('id;name;age\n1;Alice;25\n2;Bob;30')
        result = read_csv_all(csv, sep=';')

        assert len(result.dataframe) == 2
        assert list(result.dataframe.columns) == ['id', 'name', 'age']


class TestReadCsvChunks:
    """Tests for read_csv_chunks function."""

    def test_read_in_chunks(self, valid_csv):
        """Test reading CSV in chunks."""
        chunks = list(read_csv_chunks(valid_csv, chunksize=2))

        assert len(chunks) == 2  # 3 rows / chunksize 2 = 2 chunks
        assert all(isinstance(c, ReadCsvResult) for c in chunks)
        assert len(chunks[0].dataframe) == 2
        assert len(chunks[1].dataframe) == 1

    def test_chunks_with_bad_lines(self, csv_with_bad_lines):
        """Test chunked reading with malformed lines."""
        chunks = list(read_csv_chunks(csv_with_bad_lines, chunksize=2))

        assert len(chunks) > 0
        # Check that bad lines are captured per chunk
        total_bad = sum(len(c.bad_lines) for c in chunks)
        assert total_bad > 0

    def test_single_row_chunks(self, valid_csv):
        """Test reading with chunksize=1."""
        chunks = list(read_csv_chunks(valid_csv, chunksize=1))

        assert len(chunks) == 3
        assert all(len(c.dataframe) == 1 for c in chunks)

    def test_chunk_size_larger_than_file(self, valid_csv):
        """Test chunksize larger than file."""
        chunks = list(read_csv_chunks(valid_csv, chunksize=100))

        assert len(chunks) == 1
        assert len(chunks[0].dataframe) == 3


class TestReadCsv:
    """Tests for main read_csv function."""

    def test_rejects_the_pandas_iterator_without_chunksize(self, valid_csv):
        with pytest.raises(ValueError, match=r'Use read_csv_chunks\(\)'):
            read_csv(valid_csv, iterator=True)

    def test_chunks_defer_parser_option_validation_until_iteration(self, valid_csv):
        chunks = read_csv_chunks(valid_csv, chunksize=1, engine='c')
        with pytest.raises(ValueError, match='controls engine'):
            next(chunks)

    def test_read_without_chunks(self, valid_csv):
        """Test read_csv without chunking."""
        result = read_csv(valid_csv)

        assert isinstance(result, ReadCsvResult)
        assert len(result.dataframe) == 3

    def test_read_with_chunks(self, valid_csv):
        """Test read_csv with chunking."""
        result = read_csv(valid_csv, chunksize=2)

        # Should return a generator
        chunks = list(result)
        assert len(chunks) == 2
        assert all(isinstance(c, ReadCsvResult) for c in chunks)

    def test_chunksize_none_returns_result(self, valid_csv):
        """Test that chunksize=None returns ReadCsvResult not generator."""
        result = read_csv(valid_csv, chunksize=None)

        assert isinstance(result, ReadCsvResult)
        assert not hasattr(result, '__next__')

    def test_chunksize_explicit_returns_generator(self, valid_csv):
        """Test that explicit chunksize returns generator."""
        result = read_csv(valid_csv, chunksize=1)

        # Check it's a generator
        assert hasattr(result, '__next__')

    def test_kwargs_forwarded(self):
        """Test that kwargs are forwarded correctly."""
        csv = StringIO('id;name;age\n1;Alice;25')
        result = read_csv(csv, sep=';')

        assert 'Alice' in result.dataframe['name'].values


class TestIntegration:
    """Integration tests for extract module."""

    def test_read_bad_csv_file(self):
        """Test reading the actual bad.csv test file."""
        result = read_csv_all('tests/bad.csv')

        assert len(result.bad_lines) == 2
        assert len(result.dataframe) == 5
        assert 'id' in result.dataframe.columns

    def test_chunked_bad_csv_file(self):
        """Test reading bad.csv in chunks."""
        chunks = list(read_csv_chunks('tests/bad.csv', chunksize=3))

        total_bad = sum(len(c.bad_lines) for c in chunks)
        assert total_bad == 2

        total_rows = sum(len(c.dataframe) for c in chunks)
        assert total_rows == 5
