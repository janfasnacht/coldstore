# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Coldstore is transforming from a basic archiving utility into **the premier event-driven project archival system**. The tool creates immutable, verifiable project snapshots at significant events with comprehensive metadata capture.

**Current State**: Basic archiving functionality (v1.x)  
**Target State**: Event-driven archival system (v2.0) - see `IMPLEMENTATION_PLAN.md`

**Core Vision**: "When stakes are high and you need definitive proof of project state—that's when you use Coldstore."

## Implementation Status

🚧 **Active Development**: Transforming to v2.0 architecture
📋 **Implementation Plan**: See `IMPLEMENTATION_PLAN.md` for complete roadmap
🎯 **Current Phase**: Phase 1 - Core freeze engine development

**Key Transformation Areas**:
- CLI redesign: `coldstore freeze` as primary operation
- Metadata-first architecture with YAML/JSON manifests
- Streaming tar+gzip for large project handling
- Multi-level verification (archive + per-file + manifest checksums)
- Git-aware archiving with repository state capture

## Development Commands

### Setup
```bash
poetry install
```

### Current Tool (v1.x)
```bash
# Via Poetry script
poetry run coldstore <source_path> <archive_dir> [options]

# Or as module
poetry run python -m archive_project <source_path> <archive_dir> [options]
```

### Testing
```bash
make test       # Run all tests
make test-cov   # Run with coverage  
make lint       # Code linting
make lint-fix   # Auto-fix linting issues
make all-tests  # All tests and linting
```

## Current Architecture (v1.x - Legacy)

```
archive_project/
├── __init__.py          # Package initialization
├── __main__.py          # Entry point for module execution
├── cli/
│   ├── __init__.py
│   └── main.py          # Command-line interface
├── core/
│   ├── __init__.py
│   ├── archiver.py      # Main archiving logic
│   └── metadata.py      # Metadata collection
├── utils/
│   ├── __init__.py
│   ├── file_ops.py      # File operations and tree generation
│   └── formatters.py    # Formatting utilities (human sizes, README)
└── storage/
    ├── __init__.py
    └── rclone.py        # Cloud storage operations
```

**Current Components**:
- `core.archiver.archive_project()`: Main orchestration function
- `core.metadata.get_metadata()`: Basic project metadata collection
- `utils.file_ops.get_file_tree()`: Directory tree visualization  
- `utils.formatters.generate_readme()`: README generation
- `storage.rclone.upload_files()`: Cloud storage uploads

## Target Architecture (v2.0 - In Development)

**Planned Structure** (see `IMPLEMENTATION_PLAN.md`):
```
coldstore/
├── cli/                 # Typer-based CLI with freeze/verify/inspect
├── core/
│   ├── collector.py     # File system scanning + metadata capture
│   ├── builder.py       # Streaming tar+gzip creation
│   ├── manifest.py      # YAML/JSON manifest generation
│   └── verifier.py      # Multi-level integrity checking
├── metadata/
│   ├── git.py          # Git repository state capture
│   ├── environment.py  # System/environment metadata
│   └── schema.py       # Manifest schema definitions
└── storage/
    ├── local.py        # Local filesystem operations
    ├── rclone.py       # Enhanced rclone integration
    └── base.py         # Storage backend abstraction
```

**Planned CLI**:
```bash
coldstore freeze [OPTIONS] <SOURCE> <DESTINATION>  # Primary operation
coldstore verify <ARCHIVE_PATH>                    # Verification
coldstore inspect <ARCHIVE_PATH>                   # Inspection
```

## Implementation Principles (v2.0)

### Core Design Decisions (from IMPLEMENTATION_PLAN.md)
- **Event-driven mindset**: Every freeze captures a significant moment
- **Metadata-first**: Rich metadata as first-class citizen (YAML + JSON manifests)  
- **Verification as killer feature**: Multi-level integrity (archive + per-file + manifest checksums)
- **Default inclusion policy**: Include everything except VCS directories (don't respect .gitignore by default)
- **Streaming architecture**: Memory-efficient for multi-GB projects
- **One command, one purpose**: `coldstore freeze` as primary operation

### Technical Architecture Principles
- **Robustness for high-stakes**: Atomic operations, resumable processes, fail-safe defaults
- **Rich metadata capture**: Git state, environment, system info, file manifests
- **Integration-first design**: GitHub releases, cloud storage, compliance systems
- **Scalability**: Streaming compression, parallel operations, progress tracking

## Current Implementation Notes (v1.x)

- **CLI Framework**: Click-based interface (will migrate to Typer in v2.0)
- **Entry point**: Poetry script `coldstore` → `archive_project.cli.main:main`
- **Module execution**: `python -m archive_project`
- **File exclusion**: fnmatch patterns, multiple exclude patterns
- **Archive creation**: tarfile module with gzip compression (levels 1-9)
- **Checksums**: SHA256 computed in chunks for memory efficiency
- **Safety features**: Confirmation prompts for destructive operations
- **Cloud uploads**: rclone integration

## Testing Strategy

**Current (v1.x)**: 75% coverage, 30+ tests
- Core functionality, CLI interface, utility functions
- pytest with temporary directories for isolation
- CI/CD across Python 3.9-3.12 and multiple OS platforms

**Planned (v2.0)**: Enhanced testing approach
- Golden tests for deterministic archive creation
- Performance tests for large projects (10GB+)
- Integration tests with real git repositories
- Fuzz testing for exclusion patterns and edge cases

## Development Workflow

**Current Phase**: Phase 1 implementation (see `IMPLEMENTATION_PLAN.md`)
- Focus on core freeze engine with comprehensive metadata
- Streaming tar+gzip creation
- Per-file SHA256 hashing
- Git/environment metadata collection
- Manifest generation (YAML/JSON)

**Next Steps**: Break down Phase 1 into GitHub issues and begin implementation
- Design manifest schema
- Implement streaming file collector
- Build tar+gzip streaming writer
- Create CLI framework with Typer