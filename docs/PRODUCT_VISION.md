# Coldstore: Product Vision & Strategy

## Vision Statement

**Coldstore is the definitive tool for creating immutable, auditable, comprehensive project archives at significant events.**

*Not backup. Not versioning. **Definitive capture.***

## Core Value Proposition

### What Coldstore Does
Creates **event-driven project snapshots** with comprehensive metadata, verification, and integration capabilities for high-stakes moments requiring immutable records.

### What Coldstore Is NOT
- ❌ Continuous backup tool (that's Kopia, Borg, etc.)
- ❌ Version control system (that's Git)
- ❌ Simple compression utility (that's tar/zip)
- ❌ Cloud sync tool (that's rclone, rsync)

### What Coldstore IS
- ✅ **Event-driven archival**: Paper submissions, project handoffs, compliance deadlines
- ✅ **Comprehensive capture**: Code + data + environment + metadata + verification
- ✅ **Audit-ready**: Immutable, timestamped, checksummed, documented
- ✅ **Integration-aware**: Git, GitHub, compliance systems, cloud storage
- ✅ **High-stakes reliable**: Resumable, verifiable, fail-safe operations

## Target Use Cases

### 1. Academic Research Workflow
```bash
# Paper submission milestone
git tag v1.0-nature-submission
coldstore freeze --milestone "Nature submission" \
                --github-release \
                --include-environment \
                . gs://research-archives/nature-2024/
```
**Value**: Complete reproducible package for reviewers, future reference, institutional requirements.

### 2. Project Handoff
```bash
# Collaboration transfer
coldstore freeze --handoff "transfer-to-alice" \
                --include-setup-docs \
                --contact "alice@university.edu" \
                . sftp://shared-storage/projects/
```
**Value**: Self-contained package with everything needed for seamless project transition.

### 3. Compliance & Audit
```bash
# Regulatory snapshot
coldstore freeze --audit \
                --compliance "21CFR11" \
                --legal-hold \
                . compliance://vault/project-xyz/
```
**Value**: Immutable, legally defensible project state with full audit trail.

### 4. Major Milestone Capture
```bash
# Grant deliverable
coldstore freeze --milestone "phase-1-complete" \
                --deliverable "NSF-Grant-123" \
                --include-reports \
                . b2://grants/nsf-123/deliverables/
```
**Value**: Complete milestone documentation with verification and metadata.

## CLI Architecture & User Experience

### Core Commands

#### Primary Operation: `freeze`
```bash
coldstore freeze [options] <source> <destination>
```
**Philosophy**: "Freeze" implies finality, immutability, and significance—perfect for event-driven captures.

#### Secondary Operations
```bash
coldstore verify <archive>     # Verify archive integrity
coldstore inspect <archive>    # View archive metadata
coldstore resume <freeze-id>   # Resume interrupted freeze
coldstore status              # Show current/recent operations
```

### Key UX Principles

1. **Event-Centric**: Every operation should feel like capturing a significant moment
2. **Transparent**: Rich progress indicators, clear status, comprehensive logging
3. **Resumable**: Large operations can be interrupted and resumed safely
4. **Verifiable**: Every archive can be independently verified for integrity
5. **Self-Documenting**: Archives include comprehensive metadata about creation context

### Example Workflows

#### The Golden Path: Academic Submission
```bash
# 1. Tag the milestone
git tag v1.0-submission
git push origin v1.0-submission

# 2. Create comprehensive archive
coldstore freeze --milestone "PNAS submission" \
                --github-release \
                --include-git-metadata \
                --include-environment \
                --contact "researcher@university.edu" \
                --dry-run \
                . gs://research-vault/pnas-2024/

# 3. Review dry-run, then execute
coldstore freeze --milestone "PNAS submission" \
                --github-release \
                --include-git-metadata \
                --include-environment \
                --contact "researcher@university.edu" \
                . gs://research-vault/pnas-2024/

# 4. Verify and attach to GitHub release
coldstore verify gs://research-vault/pnas-2024/project_20241201_143022.tar.gz
```

#### The Compliance Path: Audit Preparation
```bash
coldstore freeze --audit \
                --compliance "SOX" \
                --retention-years 7 \
                --legal-hold \
                --encrypt-pii \
                . compliance://audit-vault/q4-2024/
```

## Technical Architecture Principles

### 1. Robustness for High-Stakes Operations
- **Atomic operations**: Either complete success or clean rollback
- **Resumable processes**: Large archives can be interrupted and resumed
- **Comprehensive verification**: Multiple integrity checks throughout process
- **Fail-safe defaults**: Conservative choices that prioritize data safety

### 2. Rich Metadata Capture
```yaml
# Generated metadata structure
archive:
  id: "project_20241201_143022"
  created: "2024-12-01T14:30:22Z"
  source: "/Users/researcher/project"
  size_bytes: 42949672960
  
event:
  type: "milestone"
  name: "PNAS submission"
  description: "Complete project archive for journal submission"
  
git:
  commit: "a1b2c3d4"
  tag: "v1.0-submission"
  branch: "main"
  dirty: false
  
environment:
  python_version: "3.11.6"
  poetry_lock_hash: "sha256:..."
  system: "Darwin 23.6.0"
  
verification:
  archive_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  file_count: 1247
  manifest_hash: "sha256:..."
  
compliance:
  audit_ready: true
  retention_policy: "7_years"
  encryption: "AES-256"
```

### 3. Integration-First Design
- **GitHub integration**: Automatic release creation, asset attachment
- **Cloud storage**: Native support for major providers (GCS, S3, B2, etc.)
- **Git awareness**: Respect .gitignore, capture git state, tag integration
- **Environment capture**: Dependencies, versions, system info

### 4. Scalability for Large Projects
- **Streaming compression**: Memory-efficient for multi-GB projects
- **Parallel operations**: Concurrent processing where safe
- **Progress tracking**: Detailed progress for long-running operations
- **Smart exclusions**: Efficient filtering of unnecessary files

## Implementation Priorities

### Phase 1: Core Freeze Operation (MVP)
**Goal**: Reliable, verifiable project archival with basic metadata

- [ ] Robust archive creation with streaming compression
- [ ] Comprehensive SHA256 verification
- [ ] Basic metadata capture (git state, environment, timestamps)
- [ ] Dry-run mode for safety
- [ ] Progress indicators for user confidence
- [ ] Local and cloud storage destinations

**Success Metric**: Can reliably archive a 10GB academic project with full verification.

### Phase 2: Event Integration
**Goal**: GitHub integration and event-driven workflows

- [ ] GitHub release integration
- [ ] Git tag awareness and automation
- [ ] Event metadata (milestones, descriptions, contacts)
- [ ] Enhanced compliance metadata
- [ ] Archive verification and inspection tools

**Success Metric**: Complete academic submission workflow from git tag to GitHub release.

### Phase 3: Enterprise Features
**Goal**: Audit, compliance, and large-scale reliability

- [ ] Resumable operations for large archives
- [ ] Compliance templates (21CFR11, SOX, etc.)
- [ ] Encryption and legal hold capabilities
- [ ] Multi-destination archival
- [ ] Advanced verification and reporting

**Success Metric**: Handle 100GB+ projects with enterprise compliance requirements.

## Current Implementation Gap Analysis

### Strengths of Current Implementation
- ✅ Basic archive creation with compression
- ✅ SHA256 verification
- ✅ Cloud storage via rclone
- ✅ Metadata README generation
- ✅ CLI structure with Click

### Critical Gaps for Vision
- ❌ **No event-driven workflow**: Current tool is generic archiving
- ❌ **No GitHub integration**: Missing core use case
- ❌ **No resumable operations**: Can't handle large projects reliably
- ❌ **Limited metadata capture**: Missing git state, environment, etc.
- ❌ **No dry-run mode**: Risk for high-stakes operations
- ❌ **Basic progress indicators**: Insufficient for large operations

### Technical Debt
- Current architecture assumes small projects
- Limited error handling and recovery
- No operation state management
- Minimal integration capabilities

## Key Design Questions & Decisions

### Open Questions

1. **CLI Command Naming**: `freeze` vs `archive` vs `snapshot`?
   - **Recommendation**: `freeze` - implies finality and immutability

2. **Configuration Management**: Project-specific vs global settings?
   - **Recommendation**: Hybrid - global defaults, project overrides in `.coldstore.yaml`

3. **Metadata Format**: JSON vs YAML vs custom?
   - **Recommendation**: YAML for human readability, JSON for machine processing

4. **Large File Handling**: Streaming vs chunking vs external references?
   - **Research needed**: Performance testing with 100GB+ projects

5. **GitHub Integration Depth**: Release creation vs full CI/CD integration?
   - **Recommendation**: Start with release creation, expand based on user feedback

### Technical Architecture Decisions

1. **Storage Backend**: Abstract interface supporting multiple providers
2. **Compression**: gzip with configurable levels (default: 6 for balance)
3. **Verification**: SHA256 for files, manifest-based for archives
4. **Metadata Storage**: Embedded in archive + external sidecar for accessibility
5. **Progress Tracking**: Event-driven with resumable state management

## Success Metrics

### User Experience Metrics
- **Time to first successful archive**: < 5 minutes from install
- **Dry-run accuracy**: 100% prediction of actual operation
- **Large project reliability**: 99%+ success rate for 10GB+ projects
- **Resume success rate**: 95%+ for interrupted operations

### Integration Metrics
- **GitHub workflow completion**: End-to-end submission workflow success
- **Cloud storage compatibility**: Support for 3+ major providers
- **Git integration accuracy**: 100% capture of git state and metadata

### Adoption Metrics
- **Primary use case coverage**: 80%+ of usage for milestone/event archival
- **Repeat usage**: Users return for multiple events (not one-off utility)
- **Community contribution**: External contributions to templates, integrations

## Competitive Positioning

| Tool | Use Case | Frequency | Output | Metadata |
|------|----------|-----------|---------|----------|
| **Kopia** | Data protection | Daily/hourly | Backup repository | Minimal |
| **Git** | Code versioning | Continuous | Repository | Code-focused |
| **tar/zip** | Basic archival | Ad-hoc | Compressed file | None |
| **Coldstore** | **Event archival** | **Milestone-driven** | **Comprehensive package** | **Rich & auditable** |

## The Bottom Line

Coldstore should be the tool researchers, engineers, and organizations reach for when they need to create a **definitive, verifiable, comprehensive record** of their project at a significant moment.

*When the stakes are high, when you need it to be perfect, when you need to prove what you had and when you had it—that's when you use Coldstore.*