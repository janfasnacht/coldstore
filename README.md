# Project Archiver CLI

A robust command-line tool for archiving research project folders with comprehensive metadata, ideal for long-term storage and project preservation.

## Features

- Create compressed `.tar.gz` archives with configurable compression levels
- Generate SHA256 checksums for integrity verification
- Create detailed README files with project metadata including:
  - File and directory counts
  - Total size in human-readable format
  - Data date range (earliest/latest file)
  - File type distribution
  - Largest files list
  - Directory structure preview
  - System information (username, hostname, OS)
- Cloud storage options (via rclone; more to come)
- Pattern-based file exclusion
- Optional deletion of original folder (with confirmation safeguards)

## Motivation

When a research project is complete, it often needs to be stored for the long term — cleanly, efficiently, and verifiably. This script provides a comprehensive, safe archiving process that thoroughly documents the project's contents, state, and size before cold storage.

## Installation

```bash
# Using pip
pip install -r requirements.txt

# Or with Poetry (recommended)
poetry install
```

## Usage

```bash
python archive_project.py <project_path> <archive_output_dir> [options]
```

### Basic Options:

- `--note "Some note"` – Add a custom note to the metadata
- `--no-archive` – Skip archive creation (generate only metadata)
- `--delete-after-archive` – Delete original folder after archiving (asks for confirmation)
- `--force` – Skip confirmation prompts (use with caution)

### Compression Options:

- `--compress-level 1-9` – Set compression level (1=fastest, 9=smallest, default=6)
- `--exclude "pattern"` – Exclude files matching pattern (can be used multiple times)

### Upload Options:

- `--upload` – Upload files to remote storage
- `--remote-path "path"` – Remote storage destination path
- `--storage-provider` – Storage provider to use (rclone)

### Examples:

```bash
# Basic archive creation
python archive_project.py ~/Projects/research ~/Archives --note "Final research data"

# Archive with exclusions and custom compression
python archive_project.py ~/Projects/analysis ~/Archives \
  --compress-level 9 \
  --exclude "*.log" \
  --exclude ".git/*" \
  --exclude "node_modules/*"

# Archive and upload to cloud storage
python archive_project.py ~/Projects/experiment ~/Archives \
  --note "Experiment results" \
  --upload \
  --remote-path "b2:research-archives/experiments" \
  --storage-provider rclone

# Create metadata only (no archive)
python archive_project.py ~/Projects/survey ~/Archives \
  --no-archive \
  --note "Survey results - metadata only"

# Archive and delete original after confirmation
python archive_project.py ~/Projects/completed ~/Archives \
  --delete-after-archive
```

## Output

The script creates three files:

```
~/Archives/
├── project_2025-03-25.tar.gz         # Compressed archive
├── project_2025-03-25.tar.gz.sha256  # SHA256 checksum
└── project_2025-03-25.README.md      # Comprehensive metadata
```

## Requirements

- Python 3.8+
- `rclone` (optional, for cloud uploads)
- `tree` command (optional, falls back to Python implementation if not available)

## Testing

Run the included tests with pytest:

```bash
# Run basic tests
pytest

# Run test with preserved output for inspection
python test_archive_project.py --preserve
```