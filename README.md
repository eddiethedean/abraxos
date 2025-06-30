# Abraxos
[![PyPI version](https://img.shields.io/pypi/v/abraxos.svg?style=flat)](https://pypi.org/project/abraxos/)
[![Documentation Status](https://readthedocs.org/projects/abraxos/badge/?version=latest)](https://abraxos.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat)](LICENSE)

**Abraxos** is a lightweight Python toolkit for robust, row-aware data processing using Pandas and Pydantic. It helps you:

- Read and clean messy CSVs
- Transform data with fault-tolerant functions
- Validate rows using Pydantic models
- Load data into SQL databases with graceful error recovery

---

## 🚀 Features

- 📄 **CSV Ingestion with Bad Line Recovery**  
  Read CSVs in full or in chunks, and recover malformed lines separately.

- 🔁 **Transform DataFrames Resiliently**  
  Apply transformation functions and isolate rows that fail.

- 🧪 **Pydantic-Based Row Validation**  
  Validate each row using a Pydantic model, separating valid and invalid records.

- 🛢️ **SQL Insertion with Error Splitting**  
  Insert DataFrames into SQL databases with automatic retry and chunking logic.

---

## 📦 Installation

```bash
pip install abraxos
```

Abraxo requires Python 3.8+ and depends on:
    - pandas
    - numpy
    - optionally sqlalchemy for SQL I/O
    - your own pydantic models for validation

---

## Documentation

Full documentation is available at:  
[https://abraxos.readthedocs.io](https://abraxos.readthedocs.io)

---

## 🧭 Usage Examples

### 🔍 Read CSVs with Error Recovery

```python
from abraxos import read_csv

bad_lines, df = read_csv("data.csv")
print("Bad lines:", bad_lines)
print("Clean data:", df.head())
```

<details> <summary>Example Output</summary>

```python
Bad lines: [['', 'oops', 'bad', 'row']]
Clean data:
   id    name  age
0   1     Joe   28
1   2   Alice   35
2   3  Marcus   40
```

</details> 

### 🧼 Transform DataFrames with Fault Isolation

```python
from abraxos import transform

def clean_data(df):
    df["name"] = df["name"].str.strip().str.lower()
    return df

result = transform(df, clean_data)
print("Errors:", result.errors)
print("Success:", result.success_df)
```

<details> <summary>Example Output</summary>

```python
Errors: []
Success:
   id    name  age
0   1     joe   28
1   2   alice   35
2   3  marcus   40
```

</details> 

### ✅ Validate Rows Using Pydantic

```python
from abraxos import validate
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int

result = validate(df, Person())
print("Valid rows:", result.success_df)
print("Validation errors:", result.errors)
```

<details> <summary>Example Output</summary>

```python
Valid rows:
   name  age
0   Joe   28

Validation errors:
[
  ValidationError: 1 validation error for Person
  age
    value is not a valid integer (type=type_error.integer),

  ValidationError: 1 validation error for Person
  name
    none is not an allowed value (type=type_error.none.not_allowed)
]
```

</details> 

### 🗃️ Insert Into SQL With Retry Logic

```python
from abraxos import to_sql
from sqlalchemy import create_engine

engine = create_engine("sqlite:///example.db")
result = to_sql(df, "people", engine)

print("Successful inserts:", result.success_df.shape[0])
print("Failed rows:", result.errored_df)
```

<details> <summary>Example Output</summary>

```python
Successful inserts: 2
Failed rows:
   name  age
2  None   40
```

</details> 



---

## 🧪 Test Coverage

Abraxo's internal structure is modular and testable. You can run tests via:

```bash
pytest tests/
```

---

## 📄 License
MIT License © 2024 Odos Matthews

---

## 🧙‍♂️ Author
Crafted by [Odos Matthews](https://github.com/eddiethedean) to bring some magic to data workflows.
