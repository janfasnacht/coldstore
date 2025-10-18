# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2025-10-18

### Added
- CLI with `coldstore freeze`, `coldstore verify`, and `coldstore inspect` commands
- Event-driven metadata capture (milestone, notes, contacts, timestamps)
- Git repository state capture (branch, commit, remotes, dirty status)
- Environment metadata (hostname, username, platform, Python version)
- Per-file SHA256 checksums for integrity verification
- Structured manifest generation (MANIFEST.json)
- Compressed file listing (FILELIST.csv.gz)
- Archive-level SHA256 checksums (SHA256SUMS)
- Dry-run mode for previewing operations
- Multi-level verification (archive + file + manifest)
- Archive inspection without extraction
- Pattern-based file exclusion
- Configurable compression levels (1-9)
- Custom archive naming
- Comprehensive test suite (295 tests)
- CI/CD pipeline for multi-platform testing (Python 3.10-3.12)
- Locked dependencies (poetry.lock) for reproducible builds

[unreleased]: https://github.com/janfasnacht/coldstore/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/janfasnacht/coldstore/releases/tag/v1.0.0
