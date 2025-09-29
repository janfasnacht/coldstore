# Coldstore: Refined Implementation Plan

## Executive Summary

Based on comprehensive analysis and expert feedback, this document outlines the definitive implementation strategy for transforming coldstore from a basic archiving tool into **the premier event-driven project archival system**.

**Core Identity**: Coldstore creates immutable, verifiable, comprehensive project snapshots at significant events—when stakes are high and you need definitive proof of project state.

**Key Principle**: "One Command, One Purpose" with metadata as a first-class citizen and verification as the killer feature.

## Core Design Principles

### 1. Simplicity & Focus
- **Single primary operation**: `coldstore freeze` - the only write operation
- **Clear supporting commands**: `verify` and `inspect` for read-only operations
- **Event-driven mindset**: Every freeze captures a significant moment

### 2. Definitive Capture
- **Default policy**: Include everything except VCS directories (.git/, .hg/, .svn/)
- **Do NOT respect .gitignore by default** - coldstore captures complete project state
- **Opt-in exclusions**: Users explicitly choose what to exclude

### 3. Metadata-First Architecture
- **Rich metadata capture**: Git state, environment, system info, file manifests
- **Dual format**: Human-readable YAML embedded, machine-readable JSON sidecar
- **Self-documenting**: Archives include comprehensive context and verification data

### 4. Verification as Killer Feature
- **Multi-level integrity**: Archive SHA256 + per-file SHA256 + manifest hash
- **Independent verification**: Archives can be verified without coldstore
- **Deterministic builds**: Reproducible archives with configurable normalization

### 5. Scalability & Robustness
- **Streaming architecture**: Memory-efficient for multi-GB projects
- **Resumable operations**: Large freezes can be interrupted and resumed
- **Comprehensive safety**: Dry-run mode, progress indicators, fail-safe defaults

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Layer (Typer)                        │
│  Commands: freeze | verify | inspect                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  Orchestrator                               │
│  - Argument validation & config loading                     │
│  - Operation state management (dry-run, resume)             │
│  - Logging, progress tracking, error handling               │
└─────────────────┬───────────────────┬───────────────────────┘
                  │                   │
┌─────────────────▼───────────────────▼───────────────────────┐
│        Collector              │        Builder              │
│  - File system scanning       │  - Streaming tar creation   │
│  - Exclusion processing       │  - Gzip compression          │
│  - Per-file SHA256 hashing    │  - Archive finalization     │
│  - Metadata capture           │  - Sidecar file generation  │
└─────────────────┬───────────────────┬───────────────────────┘
                  │                   │
                  └─────────┬─────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                  Manifest Engine                            │
│  - YAML generation (embedded)                               │
│  - JSON generation (sidecar)                                │
│  - FILELIST.csv.gz (for large projects)                     │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 Verification Engine                         │
│  - Archive integrity checking                               │
│  - Manifest consistency validation                          │
│  - Per-file hash verification                               │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 Destination Handlers                        │
│  - Local filesystem                                         │
│  - Rclone integration                                       │
│  - Future: Direct cloud APIs                                │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. CLI Command Structure
```bash
# Primary operation - the heart of coldstore
coldstore freeze [OPTIONS] <SOURCE> <DESTINATION>

# Read-only operations
coldstore verify <ARCHIVE_PATH>
coldstore inspect <ARCHIVE_PATH>
```

### 2. Default Inclusion Policy
- ✅ **Include**: All project files, data, outputs, configs
- ❌ **Exclude by default**: VCS directories (.git/, .hg/, .svn/)
- 📊 **Capture separately**: Git metadata (commit, tag, branch, dirty status)
- 🎛️ **User control**: `--respect-gitignore` flag for source-only snapshots

### 3. File Layout Strategy
```
destination/
├── coldstore_2025-09-28_22-15-03_d52b1a.tar.gz    # Main archive
├── coldstore_2025-09-28_22-15-03_d52b1a.sha256     # Archive checksum
└── coldstore_2025-09-28_22-15-03_d52b1a.MANIFEST.json  # Sidecar metadata

# Inside the tar.gz at root:
/COLDSTORE/
├── MANIFEST.yaml         # Human-readable metadata
├── README.md            # Generated summary
└── FILELIST.csv.gz      # Per-file details (for large projects)
```

### 4. Metadata Schema Design

#### Core Manifest Structure (YAML/JSON)
```yaml
manifest_version: "1.0"
created_utc: "2025-09-28T22:15:03Z"
id: "2025-09-28_22-15-03_d52b1a"

source:
  root: "/Users/jan/Projects/myproj"
  normalization:
    path_separator: "/"
    unicode_normalization: "NFC"
    ordering: "lexicographic"
    exclude_vcs: true

event:
  type: "milestone"
  name: "PNAS submission"
  note: "Frozen pre-submission state"

environment:
  system:
    os: "Darwin"
    os_version: "23.6.0"
    hostname: "jan-mbp"
  tools:
    coldstore_version: "2.0.0"
    python_version: "3.11.9"

git:
  present: true
  commit: "a1b2c3d4e5f6..."
  tag: "v1.0-submission" 
  branch: "main"
  dirty: false
  remote_origin_url: "git@github.com:org/repo.git"

archive:
  format: "tar+gzip"
  filename: "coldstore_2025-09-28_22-15-03_d52b1a.tar.gz"
  size_bytes: 4294967296
  sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  member_count:
    files: 1247
    dirs: 188
    symlinks: 4

verification:
  per_file_hash:
    algorithm: "sha256"
    manifest_hash_of_filelist: "f9ce...77ad"

files:
  - path: "README.md"
    type: "file"
    size: 1832
    mode: "0644"
    mtime_utc: "2025-09-28T19:11:04Z"
    sha256: "6fed...1240"
  # ... (truncated for large projects, full data in FILELIST.csv.gz)
```

### 5. FILELIST.csv.gz Schema
For projects with thousands of files, detailed file information stored in deterministic gzipped CSV:

| Column | Type | Description |
|--------|------|-------------|
| `relpath` | string | POSIX path relative to source root |
| `type` | enum | `file`\|`dir`\|`symlink`\|`other` |
| `size_bytes` | int | File size (empty for non-files) |
| `mode_octal` | string | File mode (e.g., "0644") |
| `uid` | int | User ID |
| `gid` | int | Group ID |
| `mtime_utc` | ISO-8601 | Last modified timestamp |
| `sha256` | hex | Content hash for files |
| `link_target` | string | Symlink target (if applicable) |
| `is_executable` | 0/1 | Execute permission flag |
| `ext` | string | File extension |

## CLI Design Specification

### `coldstore freeze` - Primary Operation

```bash
Usage: coldstore freeze [OPTIONS] <SOURCE> <DEST>

Create a deterministic, verifiable archive of SOURCE into DEST.

Arguments:
  SOURCE   Path to project root to archive
  DEST     Local directory or remote URI (with --upload)

Event & Metadata:
  --milestone TEXT          Event label (e.g., "PNAS submission")
  --note TEXT              Free-form description (repeatable)
  --contact TEXT           Contact info "Name <email>" (repeatable)

Safety & Preview:
  --dry-run               Show what would be archived without writing
  --confirm               Require interactive confirmation
  --force                 Skip confirmations (dangerous)

Inclusions & Exclusions:
  --respect-gitignore     Exclude .gitignore files (default: false)
  --exclude PATTERN       Glob pattern to exclude (repeatable)
  --exclude-from FILE     File with exclusion patterns
  --include-vcs           Include .git/ directories (default: false)

Metadata Capture:
  --include-git / --no-include-git     [default: auto-detect]
  --include-env / --no-include-env     [default: true]

Output Control:
  --name-template TEXT    Filename template (default: "coldstore_{ts}_{rand6}")
  --compression-level INT Gzip level 1-9 (default: 6)

Destinations:
  --upload REMOTE_URI     Upload via rclone (e.g., "b2:bucket/path")
  --rclone-flags TEXT     Additional rclone flags

Runtime:
  --tmpdir PATH          Temporary working directory
  --log-level [info|debug|warn]
```

### `coldstore verify` - Integrity Validation

```bash
Usage: coldstore verify [OPTIONS] <ARCHIVE_PATH>

Verify archive integrity and manifest consistency.

Options:
  --deep                 Validate all per-file hashes (slower)
  --manifest PATH        Use explicit manifest file
  --json                 Output results as JSON
```

### `coldstore inspect` - Archive Analysis

```bash
Usage: coldstore inspect [OPTIONS] <ARCHIVE_PATH>

Display archive metadata and summaries.

Options:
  --summary              High-level overview (default)
  --files                Show per-file table
  --largest N            Show N largest files
  --json                 Output raw JSON
```

## Implementation Phases

### Phase 1: Core Freeze Engine (MVP)
**Goal**: Reliable, verifiable project archival with comprehensive metadata

**Deliverables**:
- [ ] Streaming tar+gzip creation with memory efficiency
- [ ] Per-file SHA256 hashing during collection
- [ ] Comprehensive metadata capture (git, environment, system)
- [ ] MANIFEST.yaml generation (embedded) and MANIFEST.json (sidecar)
- [ ] Basic FILELIST.csv.gz for large projects
- [ ] Archive-level SHA256 verification
- [ ] Dry-run mode with accurate previews
- [ ] Local filesystem destinations
- [ ] Basic progress indicators

**Technical Milestones**:
- [ ] File system scanner with exclusion processing
- [ ] Streaming tar builder with deterministic ordering
- [ ] Metadata collector modules (git, environment, system)
- [ ] Manifest generator with dual YAML/JSON output
- [ ] CLI framework with Typer and comprehensive argument parsing

**Success Criteria**:
- ✅ Successfully freeze 10GB academic project in < 30 minutes
- ✅ Generate manifest with 100% file coverage and accurate metadata
- ✅ Dry-run predictions match actual operations within 5% size estimate
- ✅ Archive verification passes independently of coldstore

**Testing Strategy**:
- Unit tests for each component with mocked dependencies
- Integration tests with real file trees and git repositories
- Performance tests with large file sets (1000+ files, multi-GB)
- Golden tests comparing manifest output for deterministic builds

### Phase 2: Robustness & Cloud Integration
**Goal**: Production-ready reliability and cloud storage support

**Deliverables**:
- [ ] Resumable operations with checkpoint files
- [ ] Enhanced progress indicators with time estimates
- [ ] Comprehensive error handling and recovery
- [ ] Rclone integration for cloud uploads
- [ ] Advanced verification tools
- [ ] Configuration file support (.coldstore.yaml)
- [ ] Improved logging and debugging capabilities

**Technical Milestones**:
- [ ] Operation state persistence for resumable freezes
- [ ] Robust progress tracking with ETA calculations
- [ ] Rclone wrapper with error handling and retry logic
- [ ] Configuration schema and file discovery
- [ ] Enhanced CLI help and error messages

**Success Criteria**:
- ✅ Resume interrupted 50GB freeze operation successfully
- ✅ Upload archives to 3+ cloud providers (GCS, S3, B2)
- ✅ Handle network interruptions gracefully during uploads
- ✅ Provide accurate time estimates for large operations

### Phase 3: Integration & Advanced Features
**Goal**: GitHub integration and compliance capabilities

**Deliverables**:
- [ ] GitHub release integration with automatic asset attachment
- [ ] Git tag-based workflow automation
- [ ] Compliance metadata templates
- [ ] Multi-destination archival (local + cloud)
- [ ] Advanced normalization options
- [ ] Archive comparison and diff tools

**Technical Milestones**:
- [ ] GitHub API integration for release creation
- [ ] Git hooks and tag-based triggers
- [ ] Compliance metadata schemas
- [ ] Multi-destination upload orchestration
- [ ] Archive inspection and comparison tools

**Success Criteria**:
- ✅ Complete paper submission workflow from git tag to GitHub release
- ✅ Generate compliance-ready archives with audit metadata
- ✅ Support simultaneous upload to multiple cloud destinations
- ✅ Enable archive comparison for reproducibility verification

## Technical Specifications

### 1. Deterministic Build Requirements
- **Path normalization**: POSIX separators, NFC Unicode normalization
- **Lexicographic ordering**: Consistent tar member ordering
- **Timestamp handling**: Preserve filesystem mtimes by default
- **Permission normalization**: Configurable uid/gid stripping
- **Gzip determinism**: Fixed mtime=0 in gzip headers

### 2. Performance Targets
- **Memory usage**: Constant memory regardless of project size
- **Throughput**: Match tar+gzip performance within 10%
- **Scalability**: Handle 100GB+ projects with progress tracking
- **Verification speed**: Per-file hash checking at 100MB/s+

### 3. Compatibility Requirements
- **Python**: 3.9+ support across platforms
- **Dependencies**: Minimal external requirements for core functionality
- **Archive format**: Standard tar+gzip readable by any compliant tool
- **Metadata format**: JSON/YAML standards for maximum compatibility

### 4. Security Considerations
- **Path traversal**: Validate all paths and prevent directory escapes
- **Symlink safety**: Configurable symlink following with security checks
- **Checksum integrity**: Multiple verification layers prevent corruption
- **Metadata sanitization**: Careful handling of sensitive environment data

## Success Metrics

### User Experience Metrics
- **Time to first freeze**: < 5 minutes from installation to successful archive
- **Dry-run accuracy**: 95%+ prediction accuracy for size and file counts
- **Large project reliability**: 99%+ success rate for 10GB+ projects
- **Resume success rate**: 95%+ for interrupted operations > 1GB

### Technical Metrics
- **Performance**: Archive creation within 20% of raw tar+gzip speed
- **Memory efficiency**: < 100MB RAM usage regardless of project size
- **Verification speed**: Independent verification in < 10% of creation time
- **Cross-platform compatibility**: Windows, macOS, Linux support

### Adoption Metrics
- **Primary use case**: 80%+ usage for milestone/event archival
- **User retention**: 70%+ of users create multiple archives
- **Integration usage**: 50%+ of advanced users utilize GitHub integration

## Migration from Current Implementation

### Current State Analysis
The existing coldstore implementation provides:
- ✅ Basic archive creation with gzip compression
- ✅ SHA256 verification of complete archives
- ✅ Cloud storage via rclone integration
- ✅ Basic metadata README generation
- ✅ Click-based CLI framework

### Migration Strategy

#### Phase 1: Foundation Migration
1. **Preserve existing API**: Maintain backward compatibility for basic operations
2. **Extend CLI**: Add new `freeze` command while keeping current `coldstore` interface
3. **Enhance metadata**: Expand beyond basic README to comprehensive manifest
4. **Add verification**: Implement per-file hashing alongside existing archive hashes

#### Phase 2: Feature Enhancement
1. **Streaming architecture**: Replace in-memory operations with streaming
2. **Advanced CLI**: Migrate to new CLI structure with dry-run and safety features
3. **Cloud integration**: Enhance rclone integration with error handling
4. **Configuration**: Add project-specific configuration support

#### Phase 3: Complete Transition
1. **GitHub integration**: Add release automation and git-aware workflows
2. **Advanced features**: Implement resumability, compliance, multi-destination
3. **Documentation**: Complete user guide and workflow documentation
4. **Deprecation**: Phase out legacy interfaces in favor of new architecture

### Backward Compatibility
- **CLI compatibility**: Existing commands continue to work with deprecation warnings
- **Archive format**: New archives remain compatible with old verification tools
- **Configuration**: Gradual migration to new configuration schema
- **Migration tool**: Provide utility to convert old archives to new manifest format

## Implementation Priority Queue

### Immediate (Week 1-2)
1. Design and implement manifest schema
2. Create streaming file collector with SHA256 hashing
3. Build basic tar+gzip streaming writer
4. Implement dry-run mode with accurate estimation

### Short-term (Week 3-6)
1. Complete CLI framework with comprehensive argument parsing
2. Add git metadata collection and environment capture
3. Implement verification engine for manifest consistency
4. Create basic progress indicators and logging

### Medium-term (Week 7-12)
1. Add resumable operations with checkpoint persistence
2. Implement rclone integration with error handling
3. Build configuration file support and project discovery
4. Create comprehensive test suite with performance benchmarks

### Long-term (Month 4-6)
1. Develop GitHub integration and release automation
2. Add compliance metadata templates and audit features
3. Implement multi-destination upload capabilities
4. Build archive comparison and diff tools

## Conclusion

This implementation plan transforms coldstore from a basic archiving utility into a comprehensive, event-driven project archival system. By focusing on metadata richness, verification integrity, and user safety, coldstore will become the definitive tool for creating immutable project snapshots at critical moments.

The phased approach ensures steady progress while maintaining backward compatibility and user confidence. Each phase delivers tangible value while building toward the complete vision of the premier academic and professional project archival solution.