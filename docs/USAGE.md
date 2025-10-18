# coldstore Usage Guide

Comprehensive reference for coldstore commands, options, and troubleshooting.

## Table of Contents

- [Installation](#installation)
- [Command Reference](#command-reference)
  - [coldstore freeze](#coldstore-freeze)
  - [coldstore verify](#coldstore-verify)
  - [coldstore inspect](#coldstore-inspect)
- [Manifest Structure](#manifest-structure)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## Installation

### Using pipx (Recommended)

Best for CLI tools - installs in isolated environment:

```bash
pipx install coldstore
```

### Using pip

Standard Python installation:

```bash
pip install coldstore
```

### From Source

For development or latest features:

```bash
git clone https://github.com/janfasnacht/coldstore.git
cd coldstore
poetry install
poetry run coldstore --help
```

### Verify Installation

```bash
coldstore --version
coldstore --help
```

---

## Command Reference

### `coldstore freeze`

Create an immutable archive with comprehensive metadata.

#### Syntax

```bash
coldstore freeze [OPTIONS] SOURCE DESTINATION
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Path to directory to archive |
| `DESTINATION` | Yes | Directory where archive bundle will be created |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--milestone TEXT` | Text | None | Event name (e.g., "PNAS submission") |
| `--note TEXT` | Text (repeatable) | None | Descriptive note (use multiple times) |
| `--contact TEXT` | Text (repeatable) | None | Contact information (use multiple times) |
| `--name TEXT` | Text | `{dirname}-{timestamp}` | Custom archive name |
| `--compression-level INT` | 1-9 | 6 | Gzip compression (1=fast, 9=small) |
| `--exclude TEXT` | Pattern (repeatable) | None | Exclude files matching pattern |
| `--dry-run` | Flag | False | Preview without creating files |
| `--no-manifest` | Flag | False | Skip MANIFEST.json generation |
| `--no-filelist` | Flag | False | Skip FILELIST.csv.gz generation |
| `--no-sha256` | Flag | False | Skip per-file checksum computation |

#### Examples

**Basic freeze**:
```bash
coldstore freeze ~/project ./archives/ --milestone "v1.0 release"
```

**With comprehensive metadata**:
```bash
coldstore freeze ~/project ./archives/ \
    --milestone "Nature submission" \
    --note "Final version after peer review" \
    --note "Includes supplementary data" \
    --contact "PI: jane.doe@university.edu" \
    --contact "Corresponding: john.smith@university.edu"
```

**Custom naming and compression**:
```bash
coldstore freeze ~/project ./archives/ \
    --name "final-submission" \
    --compression-level 9 \
    --milestone "Final deliverable"
```

**With exclusions**:
```bash
coldstore freeze ~/project ./archives/ \
    --milestone "Archive" \
    --exclude "*.pyc" \
    --exclude "__pycache__" \
    --exclude ".venv" \
    --exclude "node_modules"
```

**Dry-run preview**:
```bash
coldstore freeze ~/project ./archives/ \
    --milestone "Test" \
    --dry-run
```

#### Output Structure

Creates a directory with these files:

```
{archive-name}/
├── {archive-name}.tar.gz    # Compressed archive
├── MANIFEST.json             # Structured metadata
├── FILELIST.csv.gz           # File listing + checksums
└── SHA256SUMS                # Archive checksum
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (invalid arguments, file access errors) |
| 2 | Source path does not exist |
| 3 | Destination is not a directory |
| 4 | Archive creation failed |

---

### `coldstore verify`

Verify archive integrity with multi-level checks.

#### Syntax

```bash
coldstore verify ARCHIVE_PATH
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `ARCHIVE_PATH` | Yes | Path to `.tar.gz` archive file |

#### Verification Levels

1. **Archive-level**: SHA256 checksum of entire `.tar.gz` file
2. **File-level**: SHA256 for each archived file (from manifest)
3. **Manifest-level**: Validates metadata structure

#### Examples

**Basic verification**:
```bash
coldstore verify ./archives/project-20251018-143022.tar.gz
```

**Verify after transfer**:
```bash
# Copy to remote server
scp ./archives/project.tar.gz server:~/

# Verify on remote
ssh server "coldstore verify ~/project.tar.gz"
```

#### Output

**Success**:
```
✓ Archive checksum valid: a3d2f1e894b7c6d5...
✓ Manifest loaded: 1,234 files
✓ Per-file checksums: 1,234/1,234 valid
✓ Archive integrity confirmed
```

**Failure**:
```
✗ Archive checksum mismatch!
  Expected: a3d2f1e894b7c6d5...
  Actual:   b4c5d6e7f8a9b0c1...
  Archive may be corrupted or tampered with.
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Verification successful |
| 1 | Archive checksum mismatch |
| 2 | File-level checksum mismatch |
| 3 | Manifest validation failed |
| 4 | Archive file not found or unreadable |

---

### `coldstore inspect`

Inspect archive contents and metadata without extraction.

#### Syntax

```bash
coldstore inspect ARCHIVE_PATH
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `ARCHIVE_PATH` | Yes | Path to `.tar.gz` archive file |

#### Displayed Information

- **Event Metadata**: Milestone, timestamp, notes, contacts
- **Git Metadata**: Branch, commit SHA, remote URLs, dirty status
- **Environment**: Hostname, username, platform, Python version
- **Archive Stats**: File count, total size, compression ratio
- **File Listing**: Paths, sizes, permissions, SHA256 checksums

#### Examples

**Basic inspection**:
```bash
coldstore inspect ./archives/project-20251018-143022.tar.gz
```

**Inspect and save output**:
```bash
coldstore inspect ./archives/project-20251018-143022.tar.gz > archive-report.txt
```

**Inspect remote archive**:
```bash
ssh server "coldstore inspect ~/archives/project.tar.gz"
```

#### Sample Output

```
=== Event Metadata ===
Milestone: Nature Neuroscience submission
Timestamp: 2025-10-18T14:30:22Z
Notes:
  - Final version after peer review
  - Includes supplementary data
Contacts:
  - PI: jane.doe@university.edu

=== Git Metadata ===
Branch: main
Commit: 7a8b9c2d4f3e1a8b9c2d4f3e1a8b9c2d4f3e1a8b
Remote: git@github.com:user/project.git
Status: Clean working directory

=== Environment ===
Hostname: research-workstation
Username: janedoe
Platform: Linux-5.15.0-x86_64
Python: 3.11.4

=== Archive Statistics ===
Files: 1,234
Total size: 456.7 MB (compressed: 127.3 MB)
Compression ratio: 3.6x
Archive SHA256: a3d2f1e894b7c6d5...

=== File Listing (first 20 files) ===
src/main.py                    1,234 bytes   0o644  d4e5f6...
src/utils.py                   2,345 bytes   0o644  e5f6a7...
...
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Inspection successful |
| 1 | Archive file not found or unreadable |
| 2 | Manifest parsing failed |

---

## Manifest Structure

Archives include a `MANIFEST.json` file with structured metadata.

### Full Manifest Schema

```json
{
  "event": {
    "milestone": "string | null",
    "timestamp": "ISO 8601 UTC",
    "notes": ["string", "..."],
    "contacts": ["string", "..."]
  },
  "git": {
    "branch": "string | null",
    "commit": "string | null",
    "remote": "string | null",
    "is_dirty": "boolean",
    "remotes": {
      "origin": "url",
      "upstream": "url"
    }
  } | null,
  "environment": {
    "hostname": "string",
    "username": "string",
    "platform": "string",
    "python_version": "string"
  },
  "archive": {
    "path": "string",
    "size_bytes": "integer",
    "sha256": "string",
    "compression_level": "integer"
  },
  "files": {
    "total_count": "integer",
    "total_size_bytes": "integer",
    "checksums": {
      "relative/path/to/file": "sha256_hash",
      ...
    }
  }
}
```

### Field Descriptions

#### Event Metadata
- `milestone`: Event name provided via `--milestone`
- `timestamp`: UTC timestamp when archive was created (ISO 8601)
- `notes`: Array of notes from `--note` options
- `contacts`: Array of contacts from `--contact` options

#### Git Metadata
- `branch`: Current Git branch (`null` if not a Git repo)
- `commit`: Full commit SHA (`null` if not a Git repo)
- `remote`: Primary remote URL (usually "origin")
- `is_dirty`: `true` if uncommitted changes exist
- `remotes`: Object mapping remote names to URLs
- Entire `git` object is `null` if Git is unavailable

#### Environment Metadata
- `hostname`: Machine hostname where archive was created
- `username`: User who created the archive
- `platform`: OS and architecture (e.g., "Linux-5.15.0-x86_64")
- `python_version`: Python version used to create archive

#### Archive Metadata
- `path`: Archive filename
- `size_bytes`: Compressed archive size in bytes
- `sha256`: SHA256 checksum of `.tar.gz` file
- `compression_level`: Gzip compression level used (1-9)

#### Files Metadata
- `total_count`: Number of files in archive
- `total_size_bytes`: Total uncompressed size of all files
- `checksums`: Object mapping file paths to SHA256 hashes

---

## Common Patterns

### Academic Research

**Paper submission with reproducibility**:
```bash
coldstore freeze ~/research/project ./archives/ \
    --milestone "Nature submission" \
    --note "Includes replication code and processed data" \
    --note "Raw data available on request (IRB restrictions)" \
    --contact "Corresponding author: prof@university.edu" \
    --exclude "data/raw/*" \
    --exclude "*.pyc"
```

**Thesis/dissertation snapshot**:
```bash
coldstore freeze ~/dissertation ./archives/ \
    --milestone "PhD dissertation defense" \
    --note "Complete dissertation with all analysis code" \
    --contact "Advisor: advisor@university.edu" \
    --name "phd-dissertation-final"
```

### Grant Management

**Annual deliverable**:
```bash
coldstore freeze ~/grants/nsf-project ./deliverables/ \
    --milestone "Year 2 Deliverable - NSF Award #1234567" \
    --note "Submitted with annual progress report" \
    --note "Data management plan compliance confirmed" \
    --contact "PI: pi@university.edu" \
    --contact "Program Officer: po@nsf.gov" \
    --name "nsf-1234567-year2"
```

**Quarterly snapshot**:
```bash
coldstore freeze ~/grants/nsf-project ./snapshots/ \
    --milestone "NSF #1234567 - Q3 2025" \
    --note "Preliminary results from simulation study" \
    --contact "PI: pi@university.edu" \
    --name "nsf-1234567-2025-q3"
```

### Project Handoffs

**Team transition**:
```bash
coldstore freeze ~/project ./handoff/ \
    --milestone "Project handoff to Team B" \
    --note "Documentation in /docs folder" \
    --note "Database credentials provided separately" \
    --contact "New lead: alice@company.com" \
    --contact "Former lead: bob@company.com" \
    --name "project-handoff-$(date +%Y%m)"
```

### Compliance & Audit

**Regulatory submission**:
```bash
coldstore freeze ~/clinical-data ./compliance/ \
    --milestone "FDA submission Q4 2025" \
    --note "Meets 21 CFR Part 11 requirements" \
    --note "IRB approval #2023-456" \
    --contact "Regulatory Affairs: compliance@pharma.com" \
    --compression-level 9 \
    --name "fda-submission-2025-q4"
```

### Software Releases

**Version release**:
```bash
coldstore freeze ~/software ./releases/ \
    --milestone "v1.0.0 release" \
    --note "Production-ready release" \
    --note "See CHANGELOG.md for full details" \
    --contact "Maintainer: dev@company.com" \
    --name "software-v1.0.0" \
    --exclude ".git" \
    --exclude "node_modules" \
    --exclude ".venv"
```

---

## Troubleshooting

### Installation Issues

**Problem**: `pipx install coldstore` fails

**Solution**:
```bash
# Ensure pipx is installed
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Restart shell, then:
pipx install coldstore
```

**Problem**: Command not found after install

**Solution**:
```bash
# Check if in PATH
which coldstore

# If not found, add to PATH (add to ~/.bashrc or ~/.zshrc):
export PATH="$PATH:$HOME/.local/bin"
```

---

### Archive Creation Issues

**Problem**: "Source path does not exist"

**Solution**:
```bash
# Verify source path exists
ls -la ~/project

# Use absolute paths
coldstore freeze /full/path/to/project ./archives/
```

**Problem**: "Permission denied" when creating archive

**Solution**:
```bash
# Check destination directory permissions
ls -ld ./archives/

# Create destination if needed
mkdir -p ./archives/

# Check source directory is readable
ls -R ~/project
```

**Problem**: Archive is much larger than expected

**Solution**:
```bash
# Use dry-run to see what's included
coldstore freeze ~/project ./archives/ --dry-run --milestone "Test"

# Add exclusions for large files
coldstore freeze ~/project ./archives/ \
    --milestone "Archive" \
    --exclude "*.log" \
    --exclude "*.tmp" \
    --exclude "data/cache/*"

# Use lower compression for faster creation (larger file)
coldstore freeze ~/project ./archives/ \
    --milestone "Archive" \
    --compression-level 1
```

**Problem**: Git metadata is `null` in manifest

**Solution**:
```bash
# Check if Git is installed
git --version

# Check if source is a Git repository
cd ~/project
git status

# Initialize Git if needed
git init
git add .
git commit -m "Initial commit"
```

**Problem**: Archive creation is very slow

**Solution**:
```bash
# Use faster compression (level 1)
coldstore freeze ~/project ./archives/ \
    --compression-level 1 \
    --milestone "Quick archive"

# Or skip per-file checksums (not recommended for integrity)
coldstore freeze ~/project ./archives/ \
    --milestone "Quick archive" \
    --no-sha256
```

---

### Verification Issues

**Problem**: "Archive checksum mismatch" after transfer

**Solution**:
```bash
# Verify file was transferred completely
ls -lh archive.tar.gz

# Re-transfer archive
scp ./archives/project.tar.gz server:~/
ssh server "coldstore verify ~/project.tar.gz"

# Check for network issues or corruption
```

**Problem**: "Manifest not found" during verification

**Solution**:
```bash
# Check if archive is valid tar.gz
tar -tzf archive.tar.gz | head

# Re-create archive if corrupt
coldstore freeze ~/project ./archives/ --milestone "Recreate"
```

---

### Inspection Issues

**Problem**: Cannot inspect remote archive

**Solution**:
```bash
# Method 1: SSH and inspect
ssh server "coldstore inspect ~/archive.tar.gz"

# Method 2: Download and inspect locally
scp server:~/archive.tar.gz ./
coldstore inspect ./archive.tar.gz
```

**Problem**: Manifest displays incorrectly

**Solution**:
```bash
# Extract and view manifest directly
tar -xzOf archive.tar.gz */MANIFEST.json | python -m json.tool
```

---

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Source path does not exist" | Invalid source directory | Check path, use absolute paths |
| "Destination is not a directory" | Destination is a file | Use directory for destination |
| "Permission denied" | Insufficient permissions | Check file/directory permissions |
| "Archive checksum mismatch" | File corruption or tampering | Re-transfer or re-create archive |
| "Git command failed" | Git not installed | Install Git or ignore Git metadata |
| "Manifest not found" | Corrupt archive | Re-create archive |

---

## Best Practices

### Archive Naming

**Use descriptive, consistent names**:
```bash
# Good: Descriptive and dated
--name "nature-submission-2025-10"
--name "nsf-1234567-year2-deliverable"
--name "project-handoff-team-b"

# Avoid: Generic or ambiguous
--name "archive"
--name "backup"
--name "test"
```

### Metadata Documentation

**Provide comprehensive context**:
```bash
# Good: Detailed and informative
--milestone "PNAS submission - Round 2 after reviewer comments"
--note "Addressed Reviewer 1 concerns on statistical methods"
--note "Added supplementary figures requested by Reviewer 2"
--note "Data files in /data directory, see DATA_README.md"
--contact "Corresponding author: jane.doe@university.edu"

# Avoid: Minimal or vague
--milestone "Submission"
--note "Final version"
```

### Git Hygiene

**Prepare repository before archiving**:
```bash
# Check status
git status

# Commit changes
git add .
git commit -m "Prepare for archival - Nature submission"

# Tag milestone
git tag -a "nature-submission" -m "Nature Neuroscience submission"

# Push to remote (ensures Git URL is accessible)
git push origin main --tags

# Then create archive
coldstore freeze . ./archives/ --milestone "Nature submission"
```

### Exclusion Patterns

**Exclude unnecessary files**:
```bash
# Python projects
--exclude "*.pyc" --exclude "__pycache__" --exclude ".venv" \
--exclude "*.egg-info" --exclude ".pytest_cache"

# Node projects
--exclude "node_modules" --exclude "dist" --exclude "build"

# General
--exclude ".DS_Store" --exclude "Thumbs.db" --exclude "*.log" \
--exclude ".git" --exclude "*.swp"

# Data caches
--exclude "data/cache/*" --exclude "data/tmp/*"
```

### Verification Workflow

**Always verify critical archives**:
```bash
# 1. Create archive
coldstore freeze ~/project ./archives/ --milestone "Important"

# 2. Verify immediately
coldstore verify ./archives/project-20251018-143022.tar.gz

# 3. After transfer
scp ./archives/project.tar.gz server:~/
ssh server "coldstore verify ~/project.tar.gz"

# 4. Before long-term storage
coldstore verify ./archives/project.tar.gz > verification-$(date +%Y%m%d).txt
```

### Compression Levels

**Choose appropriate compression**:

| Level | Use Case | Speed | Size |
|-------|----------|-------|------|
| 1 | Quick snapshots, large files | Fastest | Largest |
| 6 (default) | General use | Balanced | Medium |
| 9 | Long-term storage, uploads | Slowest | Smallest |

```bash
# Fast snapshot for daily backups
coldstore freeze ~/project ./daily/ --compression-level 1

# Balanced for most use cases (default)
coldstore freeze ~/project ./archives/

# Maximum compression for uploads/storage
coldstore freeze ~/project ./archives/ --compression-level 9
```

### Storage Strategy

**Maintain multiple copies**:
```bash
# 1. Local archive
coldstore freeze ~/project ./archives/ --milestone "Milestone"

# 2. Institutional repository
cp -r ./archives/project-20251018-143022/ /institutional-repo/

# 3. Cloud backup
rclone copy ./archives/project-20251018-143022/ remote:archives/

# 4. External drive
cp -r ./archives/project-20251018-143022/ /Volumes/Backup/

# Verify each copy
coldstore verify ./archives/project-20251018-143022.tar.gz
coldstore verify /institutional-repo/project-20251018-143022.tar.gz
coldstore verify /Volumes/Backup/project-20251018-143022.tar.gz
```

---

## Getting Help

- **CLI Help**: `coldstore --help` or `coldstore <command> --help`
- **GitHub Issues**: [github.com/janfasnacht/coldstore/issues](https://github.com/janfasnacht/coldstore/issues)
- **Discussions**: [github.com/janfasnacht/coldstore/discussions](https://github.com/janfasnacht/coldstore/discussions)
