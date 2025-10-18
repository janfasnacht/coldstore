# Contributing to coldstore

Thanks for considering contributing to coldstore!

## Development Setup

```bash
git clone https://github.com/janfasnacht/coldstore.git
cd coldstore
poetry install
```

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=coldstore --cov-report=term-missing

# Or use make
make test
make test-cov
```

## Code Quality

```bash
# Run linter
poetry run ruff check coldstore

# Auto-fix issues
poetry run ruff check --fix coldstore

# Or use make
make lint
```

## Making Changes

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature-name`
3. **Make your changes**
   - Add tests for new functionality
   - Update documentation if needed
   - Follow existing code style
4. **Run tests**: `poetry run pytest`
5. **Run linting**: `poetry run ruff check coldstore`
6. **Commit**: Use clear, descriptive commit messages
7. **Submit a pull request**

## Pull Request Guidelines

- **Keep PRs focused**: One feature or fix per PR
- **Add tests**: All new features and bug fixes should have tests
- **Update docs**: Add/update documentation for user-facing changes
- **Pass CI**: Ensure all tests pass on all Python versions (3.9-3.12)
- **Describe changes**: Explain what and why in the PR description

## Testing Guidelines

- **Write unit tests**: Test individual functions/methods
- **Write integration tests**: Test complete workflows
- **Test edge cases**: Empty inputs, large files, special characters, etc.
- **Mock external dependencies**: Use fixtures for Git operations, file I/O
- **Keep tests fast**: Avoid unnecessary file system operations

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for public functions/classes
- Keep functions focused and small
- Use descriptive variable names

## Documentation

- **README.md**: High-level overview and quick start
- **USAGE.md**: Detailed command reference
- **docs/**: Examples and guides
- **Docstrings**: API documentation in code

## Reporting Issues

- Check existing issues first
- Provide clear reproduction steps
- Include coldstore version: `coldstore --version`
- Include Python version: `python --version`
- Include OS and relevant environment details

## Feature Requests

- Open an issue to discuss before implementing
- Explain the use case and benefit
- Consider if it fits coldstore's scope

## Questions?

Open an issue or discussion on GitHub if you need help!
