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

**Academic paper submission**:
```bash
coldstore freeze ~/research/paper ./archives/ \
    --milestone "Nature submission" \
    --note "Includes replication code and data" \
    --contact "PI: prof@university.edu" \
    --exclude "data/raw/*" --exclude "*.pyc"
```

**Grant deliverable**:
```bash
coldstore freeze ~/grants/nsf-project ./deliverables/ \
    --milestone "NSF Award #1234567 - Year 2" \
    --contact "PI: pi@university.edu" \
    --contact "Program Officer: po@nsf.gov" \
    --name "nsf-1234567-year2"
```

**Project handoff**:
```bash
coldstore freeze ~/project ./handoff/ \
    --milestone "Handoff to Team B" \
    --note "See /docs for documentation" \
    --contact "New lead: alice@company.com" \
    --name "project-handoff-$(date +%Y%m)"
```

**Software release**:
```bash
coldstore freeze ~/software ./releases/ \
    --milestone "v1.0.0 release" \
    --name "software-v1.0.0" \
    --exclude ".git" --exclude "node_modules" --exclude ".venv"
```

---

## Troubleshooting

### Installation

**Command not found after install**: Add `$HOME/.local/bin` to PATH in `~/.bashrc` or `~/.zshrc`

**pipx install fails**: Ensure pipx is installed with `python3 -m pip install --user pipx`

### Archive Creation

**"Source path does not exist"**: Verify path exists, use absolute paths

**Archive larger than expected**: Use `--dry-run` to preview, add `--exclude` patterns for large files

**Git metadata is null**: Check `git status` in source directory, initialize Git if needed

**Slow creation**: Use `--compression-level 1` for faster archiving

### Verification

**"Archive checksum mismatch"**: Re-transfer archive, check for corruption

**"Manifest not found"**: Archive may be corrupt, verify with `tar -tzf archive.tar.gz | head`

### Common Errors

| Error | Solution |
|-------|----------|
| "Source path does not exist" | Check path, use absolute paths |
| "Destination is not a directory" | Use directory for destination |
| "Permission denied" | Check file/directory permissions |
| "Archive checksum mismatch" | Re-transfer or re-create archive |
| "Git command failed" | Install Git or ignore metadata |

---

## Best Practices

### Naming
Use descriptive names: `--name "nature-submission-2025-10"` instead of `--name "archive"`

### Metadata
Provide detailed context with `--milestone`, `--note`, and `--contact` options

### Git Workflow
Commit and tag before archiving:
```bash
git add . && git commit -m "Prepare for archival"
git tag -a "submission-v1" -m "Milestone tag"
git push origin main --tags
coldstore freeze . ./archives/ --milestone "Submission"
```

### Exclusions
Common patterns:
```bash
# Python: --exclude "*.pyc" --exclude "__pycache__" --exclude ".venv"
# Node: --exclude "node_modules" --exclude "dist"
# General: --exclude ".DS_Store" --exclude "*.log"
```

### Verification
Always verify after creation and transfer:
```bash
coldstore freeze ~/project ./archives/ --milestone "Test"
coldstore verify ./archives/project-*.tar.gz
```

### Compression

| Level | Use Case | Speed | Size |
|-------|----------|-------|------|
| 1 | Quick snapshots | Fastest | Largest |
| 6 (default) | General use | Balanced | Medium |
| 9 | Long-term storage | Slowest | Smallest |

---

## Getting Help

- **CLI Help**: `coldstore --help` or `coldstore <command> --help`
- **GitHub Issues**: [github.com/janfasnacht/coldstore/issues](https://github.com/janfasnacht/coldstore/issues)
- **Discussions**: [github.com/janfasnacht/coldstore/discussions](https://github.com/janfasnacht/coldstore/discussions)
