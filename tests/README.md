# Testing Guidelines for Coldstore v2.0

## Philosophy

We follow an **incremental testing approach**: write focused tests as we implement each feature, not comprehensive test suites upfront.

## Test Structure

- `conftest.py` - Shared fixtures and utilities
- `test_*.py` - Feature-specific test files

## Fixtures

### `tmp_path`
Standard pytest fixture for temporary directories.

### `sample_files`
Creates a basic file tree with:
- Multiple files and directories
- Different file types (.txt, .py, .csv)
- VCS directory (.git/)

Use for scanner, archiver, and manifest tests.

### `mock_git_repo`
Creates a minimal mock git repository structure.
Use for git metadata collection tests.

## Testing Approach by Issue

### Issue #12 (Manifest Schema)
- Test schema validation
- Test YAML/JSON round-trip
- Test required vs optional fields

### Issue #13 (File Scanner)
- Test directory walking
- Test exclusion patterns
- Test VCS filtering

### Issue #14 (Hashing)
- Test hash correctness
- Test chunked reading
- Test large file handling

### Issue #15 (Tar Builder)
- Test archive creation
- Test deterministic ordering
- Test streaming behavior

### Issue #16 (Metadata)
- Test git detection
- Test metadata extraction
- Test missing git handling

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=coldstore --cov-report=html

# Run specific test file
poetry run pytest tests/test_metadata.py

# Run with verbose output
poetry run pytest -v
```

## Coverage Goals

- **Phase 1**: 70%+ coverage on new code
- **Issue #22**: Expand to 85%+ with performance and integration tests
