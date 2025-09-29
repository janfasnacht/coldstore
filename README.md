# Coldstore

**Event-driven, verifiable project archival for high-stakes moments.**

Coldstore creates immutable, comprehensive project snapshots at significant events—paper submissions, project handoffs, compliance deadlines, major milestones. When you need definitive proof of project state, Coldstore provides auditable archives with rich metadata and multi-level verification.

## Vision & Status

🎯 **Core Mission**: Be the definitive tool for creating immutable project archives at important events

🚧 **Current Status**: In development - transforming from basic archiving utility to comprehensive event-driven archival system

📋 **Implementation**: See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for detailed roadmap

## Target Use Cases

- **Academic Research**: Paper submission snapshots with complete reproducibility metadata
- **Project Handoffs**: Self-contained packages for seamless collaboration transfers  
- **Compliance & Audit**: Immutable project states for regulatory requirements
- **Milestone Capture**: Major deliverables with comprehensive documentation

## Planned Architecture (v2.0)

**Primary Command**: `coldstore freeze` - Create definitive project snapshots
```bash
coldstore freeze --milestone "Nature submission" \
                --include-git \
                --upload "b2:research-archives" \
                . ./archives/
```

**Key Features** (in development):
- Event-driven workflow with comprehensive metadata capture
- Git-aware archiving with repository state preservation
- Multi-level verification (archive + per-file + manifest checksums)
- Streaming architecture for memory-efficient large project handling
- GitHub integration for release automation
- Resumable operations for large archives
- Compliance-ready metadata templates

## Current Implementation (v1.x - Legacy)

**Installation**:
```bash
poetry install
```

**Current Usage**:
```bash
# Via Poetry script
poetry run coldstore <source_path> <archive_dir> [options]

# Or as module  
poetry run python -m archive_project <source_path> <archive_dir> [options]
```

**Current Features**:
- Basic tar.gz archive creation with SHA256 verification
- Cloud upload via rclone integration
- README metadata generation
- File exclusion patterns
- Compression level control

**Testing**:
```bash
make test       # Run all tests
make test-cov   # Run with coverage
make lint       # Code linting
```

## Future Architecture (v2.0 - In Development)

**Planned CLI**:
```bash
# Primary operation
coldstore freeze [OPTIONS] <SOURCE> <DESTINATION>

# Verification and inspection
coldstore verify <ARCHIVE_PATH>
coldstore inspect <ARCHIVE_PATH>
```

**Enhanced Features** (coming):
- Rich manifest metadata (YAML + JSON)
- Per-file SHA256 verification  
- Git repository state capture
- Dry-run mode with accurate previews
- Resumable operations for large projects
- GitHub release integration
- Event-driven workflows

## Development Status

🏗️ **Phase 1**: Core freeze engine with comprehensive metadata capture
- Streaming tar+gzip creation
- Per-file SHA256 hashing
- Git/environment metadata collection
- Manifest generation (YAML/JSON)
- Dry-run and verification capabilities

📅 **Next Steps**: See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for detailed roadmap

## Contributing

This project is in active development. The implementation plan outlines the transformation from current basic archiving to comprehensive event-driven archival system.

**Key Areas**:
- Core archival engine development
- Metadata schema design  
- CLI interface enhancement
- GitHub integration
- Compliance features

## Requirements

- Python 3.9+
- Poetry for dependency management
- rclone (optional, for cloud uploads)
- Git (for repository metadata capture)