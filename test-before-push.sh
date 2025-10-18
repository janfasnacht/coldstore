#!/bin/bash
# Run this before pushing to catch issues locally instead of in CI

set -e  # Exit on first error

echo "🧪 Running tests locally (same as CI)..."
echo ""

poetry run pytest --cov=coldstore --cov-report=term-missing -q

echo ""
echo "✅ All tests passed! Safe to push."
