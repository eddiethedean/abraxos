# Changelog

All notable changes to abraxos will be documented in this file.

## [0.2.0]

### Changed

- Requires Python 3.11+ and pandas 2.3.3+. CI covers Python 3.11–3.14 on Linux, macOS, and Windows.
- Updated the optional integrations to SQLAlchemy 2.0.44+ and Pydantic 2.12+. NumPy is installed through pandas.
- Added a uv lockfile and CI checks for minimum dependency versions, Ruff, mypy, documentation examples, and installed wheels.
- Pushing a `v*.*.*` tag runs the full CI suite and publishes the verified distributions through PyPI Trusted Publishing when the tag matches the package version.
- Raw SQLite writes use one standalone attempt. SQLAlchemy is required for SQLite replacement and writes inside a caller transaction. SQL loads require driver autocommit to be disabled.
- CSV recovery supports one-character separators and a single header row. Short records now go to `bad_lines` alongside surplus-field records. Unrecoverable syntax raises `CsvParseError`.

### Added

- `to_sql(table=...)` accepts a SQLAlchemy table definition with single or composite primary keys.
- `validate()` supports model-shaped output and explicit input-to-serialized field mappings.
- `transform(split_on_error=False)` supports whole-frame operations. Custom SQL adapters can opt into row retries with `use_sql(retry_if=...)`.
- PostgreSQL transaction tests run in CI alongside SQLite.

### Fixed

- Full and chunked CSV reads validate record width before projection or type inference. Closing a chunk generator releases resources opened by the reader.
- Public partitions preserve pandas dtypes and indexes and allow independent assignments. Record conversion rejects duplicate column labels and maps missing values to `None`.
- Transform attempts isolate mutable cell values and check callback results before reporting success. Chunk counts below two raise `ValueError`.
- SQLAlchemy loads commit engine-owned work once and retry row failures only after a confirmed savepoint rollback. A lost transaction or operation-wide failure raises `LoadError`.
- `to_sql(table=...)` uses the supplied column types when binding values and honors explicit `dtype` overrides.
- Input-aligned validation preserves serialized values from Pydantic aliases and rejects serialization key collisions with allowed extras. Validators receive copies of nested input values, so failed rows keep their original values, dtypes, and indexes.

## [0.1.0] - 2025-10-20

**Major Update**: Modernization, bug fixes, and comprehensive testing.

### Fixed
- **Critical Bug**: Fixed missing `chunks` parameter in recursive calls to `transform()`, `to_sql()`, and `use_sql()`. Previously, the chunks parameter would reset to default (2) on recursion instead of maintaining the user-specified value.
- **Bug**: Fixed column order preservation issue in `validate()` function. Ensured output DataFrames maintain the same column order as input.
- Added `from __future__ import annotations` to all modules for Python 3.8+ compatibility with modern type hints.

### Changed
- **Breaking**: Updated minimum Python version from 3.8 to 3.10 in documentation (code still works with 3.8+ via `from __future__ import annotations`)
- Modernized all type hints to use Python 3.10+ syntax (`list` instead of `List`, `|` instead of `Union`)
- Removed redundant `@abstractmethod` decorators from Protocol classes (Protocols use structural typing)
- Updated `validate()` function to accept both Pydantic model classes and instances for better flexibility

### Added
- **New Module**: `abraxos/exceptions.py` with custom exception classes:
  - `AbraxosError` (base exception)
  - `TransformError` (transformation failures)
  - `ValidationError` (validation failures)
  - `LoadError` (SQL loading failures)
- Added `__all__` exports to all modules for explicit API surface
- Added `numpy` as explicit dependency in `pyproject.toml`
- Added optional dependency groups:
  - `dev`: Development tools (pytest, mypy, ruff, pre-commit)
  - `sql`: SQL support (sqlalchemy)
  - `validate`: Validation support (pydantic)
  - `all`: All optional dependencies
- Configured development tools in `pyproject.toml`:
  - `pytest` with coverage reporting
  - `mypy` for static type checking
  - `ruff` for fast linting and formatting
- Added comprehensive test suite:
  - `tests/conftest.py` - Shared fixtures
  - `tests/test_extract.py` - CSV reading tests (45 tests)
  - `tests/test_utils.py` - Utility function tests (24 tests)
  - `tests/test_transform.py` - Transformation tests (25 tests)
  - `tests/test_load.py` - SQL loading tests (14 tests)
  - `tests/test_validate.py` - Validation tests (21 tests)
  - `tests/test_integration.py` - End-to-end workflow tests (10 tests)
  - **Total: 118 passing tests with 92% code coverage**
- Added CI/CD configuration:
  - `.github/workflows/ci.yml` - GitHub Actions workflow
  - Tests on Python 3.10, 3.11, 3.12
  - Tests on Ubuntu, Windows, and macOS
  - Automated linting and type checking
  - Coverage reporting to Codecov
- Added `.pre-commit-config.yaml` for pre-commit hooks
- Added `CONTRIBUTING.md` with development guidelines
- Enhanced `.gitignore` with comprehensive Python project patterns

### Documentation
- Fixed typo in README: "Upgrade you Pandas" → "Upgrade your Pandas"
- Updated README examples to match actual API (e.g., `result.bad_lines` instead of unpacking)
- Updated Python version requirement in README from 3.8+ to 3.10+
- Added better development workflow documentation
- Updated all docstrings to use consistent NumPy-style format

### Internal
- Improved code organization with explicit `__all__` exports
- Better type hints throughout codebase
- More consistent error handling patterns
- Improved test coverage from ~50% to 92%

## [0.0.7] - Previous Release

See git history for previous changes.
