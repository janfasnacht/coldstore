# coldstore

[![PyPI version](https://badge.fury.io/py/coldstore.svg)](https://pypi.org/project/coldstore/)
[![Python](https://img.shields.io/pypi/pyversions/coldstore.svg)](https://pypi.org/project/coldstore/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI Status](https://github.com/janfasnacht/coldstore/actions/workflows/ci.yml/badge.svg)](https://github.com/janfasnacht/coldstore/actions)

**Freeze project snapshots into verified archives for research milestones**

A simple Python tool that creates immutable project archives with comprehensive metadata (Git state, environment details, event notes) and multi-level integrity verification. Perfect for researchers who need to preserve reproducible snapshots for paper submissions, grant deliverables, and compliance documentation.

## What it does

`coldstore` takes a project directory and creates a verified archive bundle with complete provenance:

```bash
coldstore freeze ~/research/paper ./archives/ --milestone "Nature submission"
```

Automatically captures:
- **Git metadata**: Current commit, branch, remotes, dirty status
- **Environment**: Hostname, username, platform, Python version
- **Event details**: Milestone name, timestamps, notes, contacts
- **File integrity**: Per-file SHA256 checksums for all archived files
- **Archive verification**: Multi-level checksums (archive + files + manifest)

## Quick Start

### Installation

#### Recommended (CLI tools):

```bash
pipx install coldstore
```

#### Standard Python installation:

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

### Example Output

```bash
coldstore freeze ~/research/paper ./archives/ \
    --milestone "Nature Neuroscience submission" \
    --note "Final version after reviewer comments" \
    --contact "PI: jane.doe@university.edu"
```

```
✓ Archive created: ./archives/paper-20251018-143022.tar.gz
  Size: 127.3 MB (compressed from 456.2 MB) | Files: 1,234

✓ Git metadata: main @ abc123... (https://github.com/user/paper)
✓ Event: Nature Neuroscience submission (2025-10-18T14:30:22Z)
✓ Integrity: SHA256 checksums generated for archive + 1,234 files
```

## Features

### Multi-Level Integrity Verification

```
coldstore verify archive.tar.gz

✓ Archive checksum valid: a3d2f1e8...
✓ Manifest loaded: 1,234 files
✓ Per-file checksums: 1,234/1,234 valid
✓ Archive integrity confirmed
```

### Complete Metadata Capture
Automatically captures:
- **Git state**: Branch, commit, remotes, dirty status
- **Environment**: Hostname, user, platform, Python version
- **Event details**: Milestone, timestamps, notes, contacts
- **File checksums**: SHA256 for every archived file

### Inspection Without Extraction
```bash
coldstore inspect archive.tar.gz  # View all metadata without extracting
```

### Flexible Options
- Dry-run mode for previewing operations
- Pattern-based file exclusion
- Configurable compression levels (1-9)
- Custom archive naming

## CLI Reference

```
Usage: coldstore [COMMAND] [OPTIONS]

Commands:
  freeze    Create archive with metadata
  verify    Verify archive integrity
  inspect   View archive metadata without extracting

Options (freeze):
  --milestone TEXT         Event name (e.g., "PNAS submission")
  --note TEXT             Description note (repeatable)
  --contact TEXT          Contact information (repeatable)
  --exclude TEXT          Exclude pattern (repeatable)
  --dry-run              Preview without creating files
  --compression-level INT Gzip level 1-9 [default: 6]
  --name TEXT             Custom archive name
```

### Common Usage Patterns

```bash
# Basic archival
coldstore freeze ~/project ./archives/ --milestone "Submission"
coldstore verify ./archives/project-*.tar.gz
coldstore inspect ./archives/project-*.tar.gz

# Academic paper with metadata
coldstore freeze ~/paper ./archives/ \
    --milestone "Journal submission" \
    --note "Supplementary materials included" \
    --contact "PI: prof@university.edu" \
    --exclude "*.pyc" --exclude ".venv"

# Grant deliverable
coldstore freeze ~/grant ./deliverables/ \
    --milestone "NSF Award #1234567 - Year 2" \
    --contact "PI: pi@university.edu"

# Preview before archiving
coldstore freeze ~/project ./archives/ --milestone "Test" --dry-run

# Maximum compression
coldstore freeze ~/project ./archives/ --compression-level 9
```

## Archive Structure

Each archive creates a bundle with complete provenance:

```
project-20251018-143022/
├── project-20251018-143022.tar.gz    # Compressed archive
├── MANIFEST.json                      # Complete metadata (see below)
├── FILELIST.csv.gz                    # File listing + checksums
└── SHA256SUMS                         # Archive checksum
```

The `MANIFEST.json` includes event details, Git state, environment info, and per-file checksums. See [docs/USAGE.md](docs/USAGE.md) for complete schema.

## Documentation

- **[docs/USAGE.md](docs/USAGE.md)**: Complete command reference, manifest schema, and troubleshooting
- **[CHANGELOG.md](CHANGELOG.md)**: Version history
- **[examples/](examples/)**: Real-world usage examples

## Development

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

### Quick Start

```bash
git clone https://github.com/janfasnacht/coldstore.git
cd coldstore
poetry install
poetry run pytest  # 295 tests
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
