# coldstore v1.0.0 Release Checklist

This document provides all the manual steps required to complete the v1.0.0 release.

## ✅ Completed (by Claude)

- [x] README.md polished for production
- [x] CHANGELOG.md created with v1.0.0 release notes
- [x] Examples directory created (academic_paper.md, project_milestone.md)
- [x] USAGE.md created with comprehensive documentation
- [x] pyproject.toml updated with production metadata
- [x] LICENSE file created (MIT)
- [x] GitHub release workflow created (.github/workflows/release.yml)
- [x] Pre-publication validation passed (poetry build successful, 295 tests passing)

---

## 🔴 Required User Actions

### 1. GitHub Repository Settings

**Complete these tasks to configure your GitHub repository:**

#### 1.1 Repository Description and Topics

**Option A: Via GitHub Web UI**

- [x] Go to https://github.com/janfasnacht/coldstore
- [x] Click "⚙️" (gear icon) next to "About" section
- [x] Set **Description**:
  ```
  Project archival with structured metadata (Git state, environment, notes) and multi-level integrity verification
  ```
- [x] Set **Website** (after PyPI publish): `https://pypi.org/project/coldstore/`
- [x] Click "Manage topics" and add these **6 topics** (space-separated):
  ```
  archival metadata verification research python compliance
  ```
- [x] Check "Releases" box
- [x] Click "Save changes"

**Option B: Via GitHub CLI** (faster):

```bash
cd ~/Projects/coldstore

# Set repository description
gh repo edit --description "Project archival with structured metadata (Git state, environment, notes) and multi-level integrity verification"

# Add topics
gh repo edit --add-topic archival
gh repo edit --add-topic metadata
gh repo edit --add-topic verification
gh repo edit --add-topic research
gh repo edit --add-topic python
gh repo edit --add-topic compliance

# Verify
gh repo view
```

#### 1.2 GitHub Secrets (Required for Automated Release)

- [ ] Go to https://github.com/janfasnacht/coldstore/settings/secrets/actions
- [ ] Click "New repository secret"
- [ ] Name: `PYPI_API_TOKEN`
- [ ] Value: Paste the PyPI token from step 2.3 below
- [ ] Click "Add secret"

#### 1.3 GitHub Actions Permissions (Verify)

- [ ] Go to https://github.com/janfasnacht/coldstore/settings/actions
- [ ] Under "Workflow permissions", ensure:
  - ✅ "Read and write permissions" is selected (required for creating releases)
  - ✅ "Allow GitHub Actions to create and approve pull requests" (optional)

#### 1.4 Branch Protection (Optional but Recommended)

- [ ] Go to https://github.com/janfasnacht/coldstore/settings/branches
- [ ] Click "Add branch protection rule"
- [ ] Branch name pattern: `main`
- [ ] Enable: "Require status checks to pass before merging"
  - [ ] Select: "test" (from CI workflow)
- [ ] Enable: "Require conversation resolution before merging"
- [ ] Click "Create"

---

### 2. PyPI Account Setup

#### 2.1 Create Test PyPI Account
- [ ] Visit https://test.pypi.org/account/register/
- [ ] Create account with email verification
- [ ] Enable 2FA (recommended)

#### 2.2 Create Production PyPI Account
- [ ] Visit https://pypi.org/account/register/
- [ ] Create account with email verification
- [ ] Enable 2FA (recommended)

#### 2.3 Generate API Token
- [ ] Go to https://pypi.org/manage/account/token/
- [ ] Click "Add API token"
- [ ] **Token name**: `coldstore-github-actions`
- [ ] **Scope**: Select "Entire account (all projects)" for first release
- [ ] Copy token (starts with `pypi-...`)
- [ ] **⚠️ CRITICAL**: Save token securely - you can't view it again!

#### 2.4 Add Token to GitHub Secrets
- [ ] This was completed in step 1.2 above (just verify the secret exists)

---

### 3. Pre-Release Testing (CRITICAL)

#### 3.1 Test in Clean Environment
```bash
# Create fresh virtual environment
python3 -m venv /tmp/coldstore-test
source /tmp/coldstore-test/bin/activate

# Install from built wheel
pip install /Users/jfasnacht/Projects/coldstore/dist/coldstore-1.0.0-py3-none-any.whl

# Test commands
coldstore --version
coldstore --help
coldstore freeze --help

# Create test archive
mkdir -p /tmp/test-project
echo "test" > /tmp/test-project/file.txt
coldstore freeze /tmp/test-project /tmp/test-archives --milestone "Test"

# Verify archive
coldstore verify /tmp/test-archives/test-project-*.tar.gz

# Inspect archive
coldstore inspect /tmp/test-archives/test-project-*.tar.gz

# Cleanup
deactivate
rm -rf /tmp/coldstore-test /tmp/test-project /tmp/test-archives
```

**Expected**: All commands should work without errors.

#### 3.2 Manual QA Scenarios

**Test 1: Real Project Freeze**
```bash
cd ~/Projects/coldstore
coldstore freeze . /tmp/coldstore-test-archive \
    --milestone "v1.0.0 pre-release test" \
    --note "Testing freeze on actual coldstore project" \
    --exclude ".venv" \
    --exclude "dist" \
    --exclude ".pytest_cache"

coldstore verify /tmp/coldstore-test-archive/coldstore-*.tar.gz
coldstore inspect /tmp/coldstore-test-archive/coldstore-*.tar.gz
```

**Test 2: Dry-Run Accuracy**
```bash
cd ~/Projects/coldstore
coldstore freeze . /tmp/test --milestone "Test" --dry-run > /tmp/dryrun.txt
coldstore freeze . /tmp/test --milestone "Test" > /tmp/actual.txt

# Compare file counts (should be similar)
grep -c "files" /tmp/dryrun.txt
grep -c "files" /tmp/actual.txt
```

**Test 3: Git Metadata Capture**
```bash
# Ensure clean Git state
cd ~/Projects/coldstore
git status

# Freeze with Git metadata
coldstore freeze . /tmp/test --milestone "Git test"

# Inspect and verify Git info is captured
coldstore inspect /tmp/test/coldstore-*.tar.gz | grep -A 5 "Git Metadata"
```

---

### 4. Test PyPI Publication (REQUIRED)

**⚠️ DO NOT skip this step!** Always test on Test PyPI first.

#### 4.1 Configure Test PyPI
```bash
cd ~/Projects/coldstore
poetry config repositories.test-pypi https://test.pypi.org/legacy/
```

#### 4.2 Generate Test PyPI Token
1. Go to https://test.pypi.org/manage/account/token/
2. Create API token for "Entire account"
3. Copy token

#### 4.3 Publish to Test PyPI
```bash
# Set token as environment variable (or use poetry config)
export POETRY_PYPI_TOKEN_TEST_PYPI="pypi-..."

# Publish
poetry publish -r test-pypi

# Or without env var:
poetry publish -r test-pypi -u __token__ -p pypi-YOUR_TOKEN_HERE
```

#### 4.4 Test Installation from Test PyPI
```bash
# Create clean environment
python3 -m venv /tmp/testpypi-install
source /tmp/testpypi-install/bin/activate

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            coldstore

# Test commands
coldstore --version  # Should show 1.0.0
coldstore --help

# Cleanup
deactivate
rm -rf /tmp/testpypi-install
```

**Expected**: Package installs and commands work correctly.

---

### 5. Final Code Review

#### 5.1 Verify All Changes
```bash
cd ~/Projects/coldstore
git status
git diff
```

Review:
- [x] README.md is production-ready
- [x] CHANGELOG.md has v1.0.0 section
- [x] pyproject.toml version is `1.0.0` (not `1.0.0-dev`)
- [x] LICENSE file exists
- [x] examples/ directory has content
- [x] USAGE.md is comprehensive
- [x] .github/workflows/release.yml exists

#### 5.2 Minor Linting Issues (Optional Fix)
There are 10 minor linting warnings (line length, unused import). These are non-blocking but can be fixed if desired:

```bash
# Auto-fix some issues
poetry run ruff check --fix coldstore

# Or manually address the issues in:
# - coldstore/cli/app.py (line length, f-string, complexity)
# - coldstore/core/verifier.py (line length)
# - coldstore/utils/formatters.py (unused import)
```

---

### 6. Production Release

#### 6.1 Commit All Changes
```bash
cd ~/Projects/coldstore
git add .
git status  # Review changes

git commit -m "Release v1.0.0

- Polish README.md for production
- Add comprehensive CHANGELOG.md
- Create examples/ directory with realistic use cases
- Add detailed USAGE.md documentation
- Update pyproject.toml with production metadata
- Add MIT LICENSE
- Create GitHub release workflow
- Add RELEASE_CHECKLIST.md for publication guide

Closes #22"

git push origin main
```

#### 6.2 Create and Push Tag
```bash
# Create annotated tag
git tag -a v1.0.0 -m "Release v1.0.0 - Event-driven project archival

coldstore v1.0.0 is the first production-ready release, providing
comprehensive event-driven archival with metadata and verification.

Features:
- freeze: Create immutable archives with Git, environment, and event metadata
- verify: Multi-level integrity verification (archive + file + manifest)
- inspect: Explore archives without extraction
- 295 tests, comprehensive documentation, CI/CD pipeline

Perfect for academic research, compliance, grant deliverables, and
project milestones."

# Push tag (triggers GitHub Actions release workflow)
git push origin v1.0.0
```

#### 6.3 Monitor GitHub Actions
1. Go to: https://github.com/janfasnacht/coldstore/actions
2. Watch for "Release" workflow triggered by `v1.0.0` tag
3. Workflow will:
   - Run tests on Python 3.9, 3.10, 3.11, 3.12
   - Build packages (wheel + sdist)
   - Publish to PyPI (using `PYPI_API_TOKEN` secret)
   - Create GitHub release with changelog

**Expected duration**: 5-10 minutes

If workflow fails:
- Check logs at: https://github.com/janfasnacht/coldstore/actions
- Common issues:
  - Missing `PYPI_API_TOKEN` secret (see step 2.4)
  - Version mismatch (tag vs pyproject.toml)
  - Test failures (run `poetry run pytest` locally)

#### 6.4 Verify PyPI Publication
After workflow succeeds:

1. Visit: https://pypi.org/project/coldstore/
2. Verify:
   - Version shows `1.0.0`
   - Description displays correctly
   - Metadata (keywords, classifiers) is present
   - README renders properly

#### 6.5 Test Production Installation
```bash
# Clean environment
python3 -m venv /tmp/coldstore-prod-test
source /tmp/coldstore-prod-test/bin/activate

# Install from PyPI
pipx install coldstore
# or: pip install coldstore

# Test
coldstore --version  # Should show 1.0.0
coldstore --help

# Create real archive
mkdir -p /tmp/test-project
echo "test" > /tmp/test-project/file.txt
coldstore freeze /tmp/test-project /tmp/archives --milestone "Test"

# Verify and inspect
coldstore verify /tmp/archives/test-project-*.tar.gz
coldstore inspect /tmp/archives/test-project-*.tar.gz

# Cleanup
deactivate
rm -rf /tmp/coldstore-prod-test /tmp/test-project /tmp/archives
```

---

### 7. Post-Release Verification

#### 7.1 Verify GitHub Release
1. Go to: https://github.com/janfasnacht/coldstore/releases
2. Confirm `v1.0.0` release exists
3. Check:
   - Release notes from CHANGELOG.md are included
   - Artifacts (wheel + sdist) are attached
   - Release is marked as "Latest"

#### 7.2 Update Repository About Section
1. Go to repository main page
2. Ensure description and topics are set (from step 1)
3. Add website (optional): https://pypi.org/project/coldstore/

#### 7.3 Announce (Optional)
Consider announcing on:
- GitHub Discussions: https://github.com/janfasnacht/coldstore/discussions
- Twitter/X, LinkedIn, personal website (if desired)
- Relevant communities (research computing, open science)

---

## 📊 Success Criteria

All of these should be ✅:

- [ ] Package published to PyPI at https://pypi.org/project/coldstore/
- [ ] `pipx install coldstore` works
- [ ] GitHub release created at https://github.com/janfasnacht/coldstore/releases/tag/v1.0.0
- [ ] Repository description and topics set
- [ ] All manual QA scenarios pass
- [ ] README renders correctly on PyPI and GitHub
- [ ] 295 tests passing in CI/CD

---

## 🆘 Troubleshooting

### GitHub Actions Fails

**Problem**: Release workflow fails on PyPI publish

**Solution**:
```bash
# Check if token is set correctly
# Go to: https://github.com/janfasnacht/coldstore/settings/secrets/actions
# Verify PYPI_API_TOKEN exists

# Or publish manually:
cd ~/Projects/coldstore
poetry build
poetry publish  # Uses POETRY_PYPI_TOKEN_PYPI env var or prompts
```

### Version Mismatch Error

**Problem**: "Version mismatch: tag=1.0.0, pyproject.toml=1.0.0-dev"

**Solution**:
```bash
# Verify pyproject.toml has correct version
grep "version" pyproject.toml  # Should show: version = "1.0.0"

# If not, fix and re-tag:
# 1. Edit pyproject.toml
# 2. Commit changes
# 3. Delete old tag: git tag -d v1.0.0 && git push origin :refs/tags/v1.0.0
# 4. Create new tag: git tag -a v1.0.0 -m "Release v1.0.0"
# 5. Push: git push origin v1.0.0
```

### PyPI Package Page Renders Incorrectly

**Problem**: README doesn't display well on PyPI

**Solution**:
```bash
# PyPI uses README.md specified in pyproject.toml
# Verify markdown is valid:
# - No relative links to local files
# - Images must use absolute URLs
# - GitHub-flavored markdown may not render

# Test locally:
poetry build
# Then upload and check: https://pypi.org/project/coldstore/
```

### Installation from PyPI Fails

**Problem**: `pip install coldstore` fails

**Solution**:
```bash
# Check if package exists on PyPI
curl https://pypi.org/pypi/coldstore/json

# Try installing specific version
pip install coldstore==1.0.0

# Check dependencies
pip install coldstore --verbose
```

---

## 📝 Post-Release Notes

After successful v1.0.0 release:

1. **Update development version** (for future work):
   ```bash
   # In pyproject.toml, change:
   version = "1.0.0" → version = "1.1.0-dev"

   git add pyproject.toml
   git commit -m "Bump version to 1.1.0-dev for development"
   git push origin main
   ```

2. **Close Issue #22**:
   ```bash
   gh issue close 22 --comment "v1.0.0 successfully released! 🎉

   - PyPI: https://pypi.org/project/coldstore/
   - GitHub Release: https://github.com/janfasnacht/coldstore/releases/tag/v1.0.0
   - Install: pipx install coldstore"
   ```

3. **Monitor for issues**:
   - Watch for installation issues on different platforms
   - Check for user feedback on GitHub Discussions/Issues
   - Address any critical bugs with patch releases (v1.0.1, v1.0.2)

---

## 🎉 Congratulations!

Once all steps are complete, coldstore v1.0.0 is officially released!

**Next steps**:
- Monitor PyPI download statistics
- Respond to user feedback and issues
- Plan v1.1.0 or v2.0.0 features based on user needs
- Consider adding to research computing registries/listings

---

**Questions?** Open an issue or discussion on GitHub.

**Prepared by**: Claude (implementation), Jan Fasnacht (execution)
**Date**: 2025-10-18
