# Technical Decisions & Recommendations

## Package Name: Keep "archive_project"
**Recommendation**: Keep the current name.

**Reasoning**:
- ✅ Clear and actionable - immediately tells you what it does
- ✅ Already established in the codebase and any existing users
- ✅ The terminology concern (Issue #2) can be addressed in documentation/help text
- ✅ Command `archive-project` is intuitive

While "archive_project" is project-specific, it's actually a strength - it's more memorable than generic names like "archiver" or "cold-store". We can address the terminology issue by making the help text and docs more generic.

## Structure: Go Nested
**Recommendation**: Use nested structure for clarity.

```
archive_project/
├── __init__.py
├── __main__.py          # Entry point
├── cli/
│   ├── __init__.py
│   └── main.py          # CLI logic
├── core/
│   ├── __init__.py
│   ├── archiver.py      # Main archiving logic
│   ├── metadata.py      # Metadata collection
│   └── splitter.py      # Archive splitting (future)
├── utils/
│   ├── __init__.py
│   ├── file_ops.py      # File operations
│   ├── formatters.py    # Human-readable formatting
│   └── progress.py      # Progress reporting (future)
└── storage/
    ├── __init__.py
    └── rclone.py        # Cloud storage operations
```

## CLI Framework: Stick with Click
**Recommendation**: Use Click for this project.

**Reasoning**:
- ✅ Perfect for single-command tools (which this likely stays)
- ✅ Mature, stable, well-documented
- ✅ Lighter weight than Typer for simple CLIs
- ✅ Still supports subcommands if we ever need them (unlikely)
- ✅ Better for projects that don't need complex type validation

**Typer** is excellent but shines more in multi-command applications with complex types. For a focused tool like this, Click's simplicity is a strength.

**Future commands** (if any) might be:
- `archive-project verify` - verify existing archives
- `archive-project list` - list contents without extracting
But honestly, these could just be flags on the main command.

## Testing Strategy
**Recommendation**: Start focused, expand gradually.

**Phase 1** (Now):
- pytest for test framework ✅
- Test critical paths: archiving, splitting, metadata generation
- Add GitHub Actions for running tests on PR/push

**Phase 2** (Later):
- Add `ruff` for linting (modern, fast, combines multiple tools)
- Add basic type checking with `mypy` (start permissive)
- Aim for 70%+ coverage on core functionality

**GitHub Actions Setup**:
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install poetry
      - run: poetry install
      - run: poetry run pytest
      - run: poetry run ruff check .  # Later
```

## Python Version
**Recommendation**: Bump to Python 3.9+

**Reasoning**:
- 3.8 EOL is October 2024 (very soon!)
- 3.9+ gives us:
  - Better type hints (built-in generics like `list[str]`)
  - `removeprefix()`/`removesuffix()` string methods
  - Improved dict merge operators
  - Better performance
- 3.9 is old enough to be widely available (released 2020)

## Code Style & Type Hints
**Recommendation**: Adopt modern Python practices.

**Tooling**:
```toml
[tool.ruff]
line-length = 88
target-version = "py39"
select = ["E", "F", "I", "N", "W", "UP", "B", "C90", "RUF"]

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # Start permissive
```

**Benefits**:
- Type hints catch bugs early
- Better IDE support
- Self-documenting code
- Easier onboarding for contributors

## Summary of Decisions

1. **Name**: Keep `archive_project` ✅
2. **Structure**: Nested modules ✅
3. **CLI**: Click framework ✅
4. **Testing**: pytest + GH Actions, add linting later ✅
5. **Python**: 3.9+ minimum ✅
6. **Style**: ruff + mypy + type hints ✅

These choices optimize for:
- Maintainability over clever solutions
- Gradual improvement over big-bang refactoring
- Proven tools over cutting-edge options
- Clear code over premature optimization

Ready to start implementing Task #6 with these decisions?