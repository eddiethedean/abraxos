# abraxos

**abraxos** is a Python package for reliable data transformation, validation, and database interaction. It provides utilities to handle CSV processing, SQL insertions, DataFrame transformations, and Pydantic-based validation with error tracking.

## Features
- **CSV Processing**: Read CSV files with error handling and chunking support.
- **SQL Integration**: Insert DataFrames into SQL databases with automatic error handling and retry logic.
- **Data Transformation**: Apply transformations to DataFrames while managing errors.
- **Pydantic Validation**: Validate DataFrame records using Pydantic models, separating valid and invalid rows.

## Installation
```bash
pip install abraxos
```

## Usage

### Reading CSV Files
```python
from abraxos import read_csv

bad_lines, df = read_csv("data.csv")
print("Bad lines:", bad_lines)
print(df.head())
```

### Writing Data to SQL
```python
from abraxos import to_sql

result = to_sql(df, "table_name", connection)
print("Errors:", result.errors)
print("Successful Inserts:", result.success_df.shape[0])
```

### Data Transformation
```python
from abraxos import transform

def clean_data(df):
    df["column"] = df["column"].str.lower()
    return df

result = transform(df, clean_data)
print("Errors:", result.errors)
print("Transformed Data:", result.success_df.head())
```

### Data Validation
```python
from abraxos import validate
from pydantic import BaseModel

class MyModel(BaseModel):
    column: str

result = validate(df, MyModel())
print("Errors:", result.errors)
print("Valid Data:", result.success_df.head())
```

## License
MIT License

## Contributing
Contributions are welcome! Feel free to open an issue or submit a pull request.

## Author
Developed by Odos Matthews