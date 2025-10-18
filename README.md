# coldstore

[![PyPI version](https://badge.fury.io/py/coldstore.svg)](https://pypi.org/project/coldstore/)
[![Python](https://img.shields.io/pypi/pyversions/coldstore.svg)](https://pypi.org/project/coldstore/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI Status](https://github.com/janfasnacht/coldstore/actions/workflows/ci.yml/badge.svg)](https://github.com/janfasnacht/coldstore/actions)

**Project archival with rich metadata and integrity verification**

coldstore creates compressed project archives with structured metadata (Git repository state, environment details, event notes, timestamps) and comprehensive integrity verification (archive-level, per-file, and manifest checksums).

## Quick Start

### Installation

```bash
pipx install coldstore
```

Or with pip:
```bash
pip install coldstore
```

### Basic Usage

```bash
# Create archive
coldstore freeze ~/project ./archives/ --milestone "Nature submission"

# Verify integrity
coldstore verify ./archives/project-20251018-143022.tar.gz

# Inspect without extracting
coldstore inspect ./archives/project-20251018-143022.tar.gz
```

### Example: Paper Submission

```bash
coldstore freeze ~/research/paper ./archives/ \
    --milestone "Nature Neuroscience submission" \
    --note "Final version after reviewer comments" \
    --contact "PI: jane.doe@university.edu" \
    --exclude "*.pyc" \
    --exclude "__pycache__"
```

Output:
```
✓ Archive created: ./archives/paper-20251018-143022.tar.gz
  - Size: 127.3 MB (compressed from 456.2 MB)
  - Files: 1,234
  - SHA256: a3d2f1e8...

✓ Git metadata captured:
  - Branch: main (commit: abc123...)
  - Remote: https://github.com/user/paper

✓ Event metadata:
  - Milestone: Nature Neuroscience submission
  - Timestamp: 2025-10-18T14:30:22Z
```

## Features

### Event-Driven Metadata
- Milestone/event name and timestamp
- Multiple notes and contact information
- Git repository state (branch, commit, remotes, dirty status)
- Environment details (hostname, user, platform, Python version)
- Per-file SHA256 checksums

### Multi-Level Verification
- Archive-level: SHA256 of entire `.tar.gz`
- File-level: SHA256 for each archived file
- Manifest-level: Validates metadata structure

### Inspection Without Extraction
Explore archive metadata, file listings, and statistics without extracting files.

### Dry-Run Mode
Preview what will be archived before creating files.

## CLI Reference

### `coldstore freeze`

```bash
coldstore freeze [OPTIONS] SOURCE DESTINATION

Options:
  --milestone TEXT         Event name (e.g., "PNAS submission")
  --note TEXT             Description note (repeatable)
  --contact TEXT          Contact information (repeatable)
  --name TEXT             Custom archive name
  --compression-level INT Gzip level 1-9 [default: 6]
  --exclude TEXT          Exclude pattern (repeatable)
  --dry-run              Preview without creating files
  --no-manifest          Skip MANIFEST.json generation
  --no-filelist          Skip FILELIST.csv.gz generation
  --no-sha256            Skip per-file checksums
```

### `coldstore verify`

```bash
coldstore verify ARCHIVE_PATH
```

Performs three-level verification:
- Archive checksum (SHA256 of `.tar.gz`)
- Per-file checksums (from manifest)
- Manifest structure validation

### `coldstore inspect`

```bash
coldstore inspect ARCHIVE_PATH
```

Displays:
- Event metadata (milestone, notes, contacts, timestamp)
- Git state (branch, commit, remote, dirty status)
- Environment (hostname, user, platform)
- Archive statistics (file count, sizes)
- File listing with checksums

## Common Patterns

```bash
# Academic paper with exclusions
coldstore freeze ~/paper ./archives/ \
    --milestone "Journal submission" \
    --note "Supplementary materials included" \
    --contact "Corresponding: prof@university.edu" \
    --exclude "*.pyc" --exclude ".venv"

# Grant deliverable
coldstore freeze ~/grant-project ./deliverables/ \
    --milestone "NSF Year 2 Deliverable - Award #1234567" \
    --contact "PI: pi@university.edu" \
    --contact "Program Officer: po@nsf.gov"

# Dry-run preview
coldstore freeze ~/project ./archives/ --milestone "Test" --dry-run

# Maximum compression for long-term storage
coldstore freeze ~/project ./archives/ \
    --compression-level 9 \
    --milestone "Archive"
```

## Archive Structure

```
project-20251018-143022/
├── project-20251018-143022.tar.gz    # Compressed archive
├── MANIFEST.json                      # Structured metadata
├── FILELIST.csv.gz                    # File listing + checksums
└── SHA256SUMS                         # Archive checksum
```

### MANIFEST.json

```json
{
  "event": {
    "milestone": "Nature submission",
    "timestamp": "2025-10-18T14:30:22Z",
    "notes": ["Final version"],
    "contacts": ["PI: jane.doe@university.edu"]
  },
  "git": {
    "branch": "main",
    "commit": "abc123...",
    "remote": "https://github.com/user/repo",
    "is_dirty": false
  },
  "environment": {
    "hostname": "workstation",
    "username": "user",
    "platform": "Linux-5.15.0-x86_64",
    "python_version": "3.11.4"
  },
  "archive": {
    "path": "project-20251018-143022.tar.gz",
    "size_bytes": 133456789,
    "sha256": "a3d2f1e8..."
  },
  "files": {
    "total_count": 1234,
    "total_size_bytes": 456789012,
    "checksums": {
      "src/main.py": "d4e5f6...",
      ...
    }
  }
}
```

## Documentation

- **[docs/USAGE.md](docs/USAGE.md)**: Detailed command reference and troubleshooting
- **[CHANGELOG.md](CHANGELOG.md)**: Version history

## Requirements

- Python 3.9+
- Git (optional, for repository metadata)

## Development

### Setup

```bash
git clone https://github.com/janfasnacht/coldstore.git
cd coldstore
poetry install
poetry run pytest  # 295 tests
```

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

### Testing

```bash
make test       # Run all tests
make test-cov   # With coverage
make lint       # Code quality checks
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
