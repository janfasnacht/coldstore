# Phase 1 GitHub Issues Draft

Draft issues for v2.0 Phase 1: Core Freeze Engine. These are intentionally high-level to allow for learning and adaptation during implementation.

---

## Issue 12: Design and implement manifest schema

**Labels**: `v2.0`, `phase-1`, `metadata`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Design the manifest schema for YAML/JSON format that captures comprehensive project metadata. Include structures for source info, event metadata, git state, environment, archive details, and verification data.

**Key Deliverables**:
- Define manifest schema (version 1.0)
- Implement Python dataclasses/pydantic models
- Support dual YAML (embedded) and JSON (sidecar) output
- Design FILELIST.csv.gz schema for large projects

**References**: See `IMPLEMENTATION_PLAN.md` lines 117-196 for schema examples.

---

## Issue 13: Implement file system scanner with exclusion processing

**Labels**: `v2.0`, `phase-1`, `core`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Build a file system scanner that walks directory trees and processes exclusion patterns. Should handle default VCS exclusions, optional .gitignore respect, and custom exclude patterns.

**Key Deliverables**:
- Recursive directory scanner
- Exclusion pattern matching (glob-based)
- VCS directory filtering (.git/, .hg/, .svn/)
- Optional .gitignore integration
- Memory-efficient iterator pattern

---

## Issue 14: Add per-file SHA256 hashing during collection

**Labels**: `v2.0`, `phase-1`, `verification`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Implement per-file SHA256 hashing as files are scanned. Hashes should be computed efficiently (chunked reads) and stored for manifest generation.

**Key Deliverables**:
- Chunked file reading for memory efficiency
- SHA256 computation per file
- Hash storage in file metadata structure
- Performance optimization for large files

---

## Issue 15: Build streaming tar+gzip archive builder

**Labels**: `v2.0`, `phase-1`, `core`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Create a streaming tar builder that writes files to a gzipped tarball incrementally without loading entire archives into memory. Support deterministic ordering for reproducible builds.

**Key Deliverables**:
- Streaming tar creation using Python tarfile
- Gzip compression with configurable levels
- Deterministic file ordering (lexicographic)
- Memory-efficient design (constant memory usage)
- Archive-level SHA256 generation

---

## Issue 16: Implement metadata collectors (git, environment, system)

**Labels**: `v2.0`, `phase-1`, `metadata`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Build modular metadata collectors that capture git repository state, system information, and environment details.

**Key Deliverables**:
- Git metadata: commit hash, branch, tag, dirty status, remote URL
- System metadata: OS, hostname, architecture
- Environment metadata: Python version, coldstore version
- Tool detection (git availability)
- Clean separation of concerns (modular collectors)

---

## Issue 17: Generate MANIFEST files (YAML embedded + JSON sidecar)

**Labels**: `v2.0`, `phase-1`, `metadata`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Implement manifest generation that produces both embedded YAML (inside archive) and JSON sidecar files. Include FILELIST.csv.gz generation for large projects.

**Key Deliverables**:
- YAML manifest embedded in archive at `/COLDSTORE/MANIFEST.yaml`
- JSON sidecar file (`*.MANIFEST.json`)
- FILELIST.csv.gz for detailed file listings
- Deterministic CSV ordering for reproducibility
- Manifest hash computation

---

## Issue 18: Implement `coldstore freeze` CLI with Typer

**Labels**: `v2.0`, `phase-1`, `cli`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Migrate CLI from Click to Typer and implement the new `coldstore freeze` command structure with comprehensive argument parsing.

**Key Deliverables**:
- Typer-based CLI framework
- `coldstore freeze <SOURCE> <DEST>` command
- Event metadata options (--milestone, --note, --contact)
- Exclusion options (--exclude, --respect-gitignore, --include-vcs)
- Output control options (--name-template, --compression-level)
- Backward compatibility consideration for existing CLI

**References**: See `IMPLEMENTATION_PLAN.md` lines 197-241 for full CLI spec.

---

## Issue 19: Add dry-run mode with accurate previews

**Labels**: `v2.0`, `phase-1`, `cli`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Implement `--dry-run` mode that shows what would be archived without writing files. Should provide accurate size estimates and file counts.

**Key Deliverables**:
- `--dry-run` flag implementation
- Preview of files to be archived
- Size estimation (compressed and uncompressed)
- File count summaries
- No-op mode for archive writing

**Success Metric**: Predictions within 5% of actual operations.

---

## Issue 20: Implement archive verification tools

**Labels**: `v2.0`, `phase-1`, `verification`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Build verification tools that validate archive integrity using SHA256 checksums and manifest consistency checks.

**Key Deliverables**:
- Archive-level SHA256 verification (.sha256 file)
- Manifest consistency validation
- Per-file hash verification (optional deep mode)
- Standalone verification (independent of coldstore)
- `coldstore verify` command (basic version)

---

## Issue 21: Add basic progress indicators

**Labels**: `v2.0`, `phase-1`, `cli`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Implement basic progress indicators during freeze operations to show user what's happening.

**Key Deliverables**:
- File processing progress display
- Current file being processed
- Basic stats (files processed, data written)
- Clean logging output
- No ETA required for Phase 1 (simple is fine)

---

## Issue 22: Build comprehensive test suite for Phase 1

**Labels**: `v2.0`, `phase-1`, `testing`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Create comprehensive tests covering Phase 1 functionality including unit tests, integration tests, and performance tests.

**Key Deliverables**:
- Unit tests for scanner, hasher, builder, collectors
- Integration tests with real file trees and git repos
- Performance tests with large file sets (1000+ files)
- Golden tests for manifest determinism
- CI/CD integration

**Success Criteria**:
- Successfully freeze 10GB academic project in < 30 minutes
- Generate manifest with 100% file coverage
- Dry-run predictions within 5% accuracy
- Archive verification passes independently

---

## Issue 23: Implement `coldstore inspect` command (basic)

**Labels**: `v2.0`, `phase-1`, `cli`
**Milestone**: v2.0 Phase 1: Core Freeze Engine

### Description
Add basic archive inspection command that displays manifest metadata and summaries without extracting the archive.

**Key Deliverables**:
- `coldstore inspect <ARCHIVE_PATH>` command
- Display high-level metadata (source, event, git info)
- Archive statistics (file counts, sizes)
- Human-readable summary output
- JSON output option (`--json`)

**References**: See `IMPLEMENTATION_PLAN.md` lines 256-268 for CLI spec.

---

## Notes

- **Total issues**: 12 new issues (12-23)
- **Existing open issues**: 3, 5, 8, 9, 10, 11 (can be moved to Phase 2/3 or kept as backlog)
- **Implementation approach**: Start with foundational issues (12-16), then CLI (17-19), then verification/inspection (20, 23), then testing (22)
- **Flexibility**: Issues are intentionally high-level to allow for discovery during implementation
- **Testing**: Issue 22 should be tackled incrementally as other issues are completed
