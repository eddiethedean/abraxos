# Contributing to Abraxos

Thank you for considering contributing to Abraxos! This document outlines the process and guidelines for contributing.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/eddiethedean/abraxos.git
   cd abraxos
   ```

2. **Install dependencies with uv and set up the hooks**
   ```bash
   uv sync --locked --python 3.11
   uv run --locked pre-commit install
   ```

## Development Workflow

Run the tests, lint, type check, then build the documentation and run its examples.

```bash
uv run --locked pytest -W error
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy abraxos
uv run --locked sphinx-build -W -b html docs docs/_build/html
uv run --locked sphinx-build -W -b doctest docs docs/_build/doctest
```

Use `uv run --locked pytest tests/test_extract.py` to run a single
file and `uv run --locked pytest --cov-report=html` for HTML coverage.
Use `uv lock --upgrade` when updating the resolved dependencies.

Set `ABRAXOS_TEST_POSTGRES` to a `postgresql+psycopg://` URL for a test
database where the connected role can create schemas. The tests create a
separate schema for each case. Run them with
`uv run --locked --group postgres pytest -W error -m postgres`.

## Code Guidelines

### Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use single quotes for strings (enforced by ruff)

### Documentation

- All public functions must have docstrings
- Use NumPy-style docstrings
- Include examples in docstrings where helpful
- Keep README.md up to date

### Testing

- Write tests for all new features
- Maintain or improve code coverage (target: 90%+)
- Test both success and failure paths
- Include edge cases (empty DataFrames, single rows, etc.)

### Type Hints

- Target Python 3.11 and use built-in generics and `|` unions.
- Type hint all function parameters and return values
- Use Protocol classes for structural typing

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code following the guidelines above
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests and checks**
   ```bash
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked mypy abraxos
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add feature: description"
   ```

   Commit message guidelines:
   - Use present tense ("Add feature" not "Added feature")
   - First line: brief summary (50 chars or less)
   - Detailed description if needed (wrap at 72 chars)

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a pull request on GitHub

6. **PR Review**
   - Ensure all CI checks pass
   - Address review feedback
   - Keep PR focused and reasonably sized

## Release Workflow

Update `abraxos.__version__` and the changelog, then verify the distributions.

```bash
uv build --no-sources
uv run --locked twine check --strict dist/*.whl dist/*.tar.gz
```

Once CI passes on the release commit, create and push a `v*.*.*` tag that
matches the package version.

```bash
git tag -a v0.2.0 -m "Release 0.2.0"
git push origin v0.2.0
```

Pushing the tag triggers `.github/workflows/release.yml`. It runs the same
checks as commit CI and verifies that the built wheel's version matches the
tag. After the checks pass, it publishes the verified distributions through
the `pypi` environment using PyPI Trusted Publishing.

## Bug Reports

When reporting bugs, please include:

- Python version
- Abraxos version
- Minimal reproducible example
- Expected vs actual behavior
- Error messages and stack traces

## Feature Requests

For feature requests:

- Describe the problem you're trying to solve
- Explain your proposed solution
- Consider backward compatibility
- Be open to discussion and alternative approaches

## Questions?

- Check the [documentation](https://abraxos.readthedocs.io)
- Open an issue for questions
- Join discussions in existing issues/PRs

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards other community members

Thank you for contributing to Abraxos! 🎉
