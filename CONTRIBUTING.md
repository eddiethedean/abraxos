# Contributing to Abraxos

Thank you for considering contributing to Abraxos! This document outlines the process and guidelines for contributing.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/eddiethedean/abraxos.git
   cd abraxos
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev,sql,validate]"
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

## Development Workflow

### Running Tests

Run the full test suite:
```bash
pytest
```

Run with coverage report:
```bash
pytest --cov=abraxos --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_extract.py
```

### Code Quality

**Linting and Formatting**
```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

**Type Checking**
```bash
mypy abraxos
```

### Pre-commit Hooks

Pre-commit hooks will run automatically on `git commit`. To run manually:
```bash
pre-commit run --all-files
```

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

- Use Python 3.10+ syntax: `list` instead of `List`, `|` instead of `Union`
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
   pytest
   ruff check .
   mypy abraxos
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

