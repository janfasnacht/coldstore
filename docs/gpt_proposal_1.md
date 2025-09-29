Great—here are the three deliverables, kept tight and implementation-ready.

---

# 1) Manifest schema proposal

## Goals

* Human-readable and machine-parseable.
* Complete provenance + integrity (archive hash + per-file hashes).
* Deterministic reproduction (document normalization rules used to build the archive).
* Sidecar + embedded: same content saved as `MANIFEST.yaml` (embedded) and `MANIFEST.json` (sidecar).

### File layout (recommended)

```
<dest>/
  coldstore_<id>.tar.gz
  coldstore_<id>.sha256           # SHA256 of the .tar.gz
  coldstore_<id>.MANIFEST.json    # JSON sidecar (same content as embedded YAML)
  # inside the tar at root:
  /COLDSTORE/
    MANIFEST.yaml
    README.md                     # human summary (pretty-printed from manifest)
    FILELIST.csv.gz               # optional: gzip’d per-file table (for huge trees)
```

### Manifest (YAML) — canonical fields

```yaml
manifest_version: "1.0"
created_utc: "2025-09-28T22:15:03Z"
id: "2025-09-28_22-15-03_d52b1a"            # stable slug (datetime + short random)
source:
  root: "/Users/jan/Projects/myproj"
  relativization: "strip_prefix"            # how paths were made relative
  include_git_ignored: false
  follow_symlinks: false
  exclusions:
    - "*.log"
    - ".git/*"
  normalization:
    path_separator: "/"                     # paths in manifest/tar normalized to "/"
    unicode_normalization: "NFC"
    owner_mapping: "preserve"               # or "strip" (uid/gid -> 0:0), "map"
    mode_mask: "preserve"                   # or e.g. "0755 for dirs, 0644 for files"
    mtime_source: "filesystem"              # or "fixed:<timestamp>" for reproducible builds
    ordering: "lexicographic"               # tar member ordering rule

event:
  type: "milestone"                         # e.g., milestone|handoff|audit|deliverable|general
  name: "PNAS submission"
  note: "Frozen pre-submission state"

environment:
  system:
    os: "Darwin"
    os_version: "23.6.0"
    hostname: "jan-mbp"
    user: "jan"
  tools:
    coldstore_version: "0.3.0"
    python_version: "3.11.9"
    tar_impl: "libtar-python"
    compressor: "gzip"
    compressor_level: 6
  runtime:
    locale: "en_US.UTF-8"
    timezone: "America/Chicago"
  dependencies:
    # Optional: hashes of lockfiles etc.
    poetry_lock_sha256: "9b0f...e12a"
    requirements_txt_sha256: null

git:
  present: true
  workdir_inside_source: true
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
    others: 0
  data_time_range:
    earliest_mtime_utc: "2022-06-01T12:03:33Z"
    latest_mtime_utc:   "2025-09-28T20:57:01Z"

verification:
  per_file_hash:
    algorithm: "sha256"
    manifest_hash_of_filelist: "f9ce...77ad"     # hash over concatenated file entries (see below)
  deterministic_build:
    enabled: true
    knobs:
      fixed_mtime: null
      strip_ownership: false
      canonical_ordering: true

destinations:
  primary:
    uri: "file:///Users/jan/Archives"
  uploads:
    - kind: "rclone"
      remote: "b2:research-archives/coldstore"
      object: "coldstore_2025-09-28_22-15-03_d52b1a.tar.gz"
      checksum_verified: true

contacts:
  owner: { name: "Jan Fasnacht", email: "jan@example.com" }
  additional: []

# Compact inventory for quick read; full CSV available separately if large
files:
  # Each entry is relative to source.root; lexicographically sorted
  - path: "README.md"
    type: "file"
    size: 1832
    mode: "0644"
    uid: 501
    gid: 20
    mtime_utc: "2025-09-28T19:11:04Z"
    sha256: "6fed...1240"
  - path: "data/sample.parquet"
    type: "file"
    size: 10485760
    mode: "0644"
    uid: 501
    gid: 20
    mtime_utc: "2025-09-15T08:55:32Z"
    sha256: "af03...bb91"
  - path: "scripts"
    type: "dir"
    mode: "0755"
    uid: 501
    gid: 20
    mtime_utc: "2025-09-10T10:01:00Z"
  - path: "bin/tool"
    type: "symlink"
    link_target: "../.venv/bin/tool"
    mtime_utc: "2025-09-10T10:01:00Z"

summaries:
  counts_by_extension:
    .py: 73
    .ipynb: 4
    .parquet: 12
    .csv: 18
    .pdf: 6
    other: 1134
  top_largest:
    - path: "data/big/part-0001.parquet"
      size: 1073741824
      sha256: "c201...aa09"
    - path: "models/model.bin"
      size: 512000000
      sha256: "0d33...41f2"
  tree_preview:
    max_depth: 2
    sample:
      - "data/"
      - "data/big/"
      - "scripts/"
      - "src/"

notes:
  - "Created with dry-run preview before final freeze."
  - "Respects .gitignore by default."
```

#### Notes & rules

* **Per-file list** MUST be present. For huge trees, keep full details in `FILELIST.csv.gz` and store a **hash of that table** in `verification.manifest_hash_of_filelist`. The `files` array in YAML can be truncated with `files_truncated: true` if needed, but not in MVP.
* All timestamps in UTC ISO-8601.
* Paths are **relative**, POSIX separators, NFC.
* The **archive.sha256** is the checksum of the `.tar.gz` blob as written to disk/remote.
* Determinism: if `deterministic_build.enabled` is true, document which knobs were applied; MVP supports canonical ordering; optional future knobs may include fixed mtime, owner stripping.

---

# 2) MVP architecture diagram (module layout)

```
+-------------------------------------------------------------+
|                          CLI (Typer/Click)                  |
|  - commands: freeze | verify | inspect                      |
+-------------------------+-----------------------------------+
                          |
                          v
+-------------------------------------------------------------+
|                    Orchestrator (core.run)                  |
| - Validates args, loads config (.coldstore.yaml)            |
| - Wires components, handles dry-run, logging, exit codes    |
| - Produces OperationState (id, temp dirs, checkpoints)      |
+-------------------------+-----------------------------------+
                          |
     +--------------------+----------------------+
     |                                           |
     v                                           v
+------------+                          +---------------------+
| Collector  |                          |   Builder/Writer    |
| (metadata) |                          |  (archive pipeline) |
+------------+                          +---------------------+
| - FS scan (walk)                      | - Tar stream (sorted entries)
| - Exclusions (.gitignore, globs)      | - Gzip compressor (level N)
| - File stats (size, mode, mtime)      | - Member header normalization
| - Per-file SHA256 (streamed)          | - Write /COLDSTORE/ payloads
| - System info, env, git state         | - Finalize archive, compute SHA256
| - Summaries (counts, top_largest)     | - Persist sidecar files
+------------+                          +---------------------+
     |                                           |
     | manifest data                             |
     +--------------------+----------------------+
                          v
                 +-------------------+
                 |   Manifest I/O    |
                 +-------------------+
                 | - Build manifest (dict)
                 | - Emit YAML (embedded)
                 | - Emit JSON (sidecar)
                 | - Optional FILELIST.csv.gz
                 +-------------------+

                          |
                          v
                 +-------------------+
                 |   Verification    |
                 +-------------------+
                 | - archive .sha256 |
                 | - re-hash filelist|
                 | - cross-check     |
                 +-------------------+

                          |
                          v
                 +-------------------+
                 |   Destinations    |
                 +-------------------+
                 | - Local fs        |
                 | - Rclone wrapper  |
                 | - (future: S3/GCS)|
                 +-------------------+

                          |
                          v
                 +-------------------+
                 |   Inspect (RO)    |
                 +-------------------+
                 | - Pretty print    |
                 | - Summaries       |
                 | - Diff manifests* |
                 +-------------------+
```

**MVP boundaries**

* Implement: Collector, Builder/Writer (streaming tar+gzip), Manifest I/O, Verification, Local + rclone uploads, Inspect (pretty).
* Defer: resumable checkpoints beyond a simple “resume same temp dir if present”; compliance templates; encryption.

---

# 3) CLI help output mockup

### `coldstore --help`

```
Usage: coldstore [OPTIONS] COMMAND [ARGS]...

Event-driven, verifiable project archiver.

Commands:
  freeze   Create an immutable archive + manifest for a source directory.
  verify   Verify archive integrity against its manifest and checksums.
  inspect  Display manifest summaries and details.

Options:
  -v, --version   Show version and exit.
  -h, --help      Show this message and exit.
```

### `coldstore freeze --help`

```
Usage: coldstore freeze [OPTIONS] <SOURCE> <DEST>

Create a deterministic, verifiable archive ("freeze") of SOURCE into DEST.
Writes:
  - tar.gz archive
  - .sha256 archive checksum
  - MANIFEST.json sidecar
  - Embedded MANIFEST.yaml + README.md (+ optional FILELIST.csv.gz) inside /COLDSTORE

Arguments:
  SOURCE   Path to project root to archive.
  DEST     Directory or remote URI (via rclone if --upload is used).

Core options:
  --milestone TEXT           Short human label for the event (e.g., "PNAS submission").
  --note TEXT                Free-form note to embed in manifest (repeatable).
  --contact TEXT             Contact email or "Name <email>" (repeatable).

Safety & preview:
  --dry-run                  Show what would be archived (counts, size estimate, exclusions).
  --confirm                  Require interactive confirmation before writing.
  --force                    Skip confirmations (dangerous).

Inclusions & exclusions:
  --respect-gitignore / --no-respect-gitignore   [default: respect]
  --exclude PATTERN          Glob to exclude (repeatable).
  --exclude-from FILE        File with one glob per line.
  --follow-symlinks          Follow symlinks (default: false).

Determinism & normalization:
  --canonical-ordering       Sort entries lexicographically (default: true).
  --strip-ownership          Store 0:0 for uid/gid (default: false).
  --fixed-mtime ISO8601      Force fixed mtime for all entries (optional).
  --mode-mask TEXT           Mode policy: "preserve" (default) or e.g. "0644/0755".

Metadata capture:
  --include-git / --no-include-git               [default: include if repo detected]
  --include-env / --no-include-env               [default: true]

Compression:
  --compressor [gzip]       Compressor (MVP: gzip).
  --level INTEGER           Compression level 1-9 (default: 6).

Output naming:
  --name-template TEXT      Filename template (default: "coldstore_{ts}_{rand6}").
                            Variables: {ts}, {rand6}, {milestone}
  --id TEXT                 Override generated operation id (advanced).

Uploads:
  --upload REMOTE_URI       Upload archive via rclone (e.g., "b2:bucket/path").
  --rclone-flags TEXT       Extra flags passed to rclone (advanced).

Runtime:
  --tmpdir PATH             Temporary working directory.
  --log-level [info|warn|debug]
  -h, --help                Show this message and exit.
```

### `coldstore verify --help`

```
Usage: coldstore verify [OPTIONS] <ARCHIVE_PATH_OR_URI>

Verify an archive against its checksums and embedded/sidecar manifest.

Checks:
  - archive .sha256 file matches
  - embedded manifest integrity
  - per-file SHA256s (requires read access to archive contents)
  - FILELIST.csv.gz hash if present

Options:
  --deep                      Validate all per-file hashes (can be slow).
  --manifest PATH             Use explicit manifest file instead of embedded/sidecar.
  --rclone-flags TEXT         Extra flags for fetching remote archives.
  --log-level [info|warn|debug]
  -h, --help
```

### `coldstore inspect --help`

```
Usage: coldstore inspect [OPTIONS] <ARCHIVE_PATH_OR_MANIFEST>

Pretty-print manifest summaries and details without modifying anything.

Options:
  --summary                   Show high-level overview (default).
  --files                     Show per-file table (paginated).
  --largest N                 Show N largest files.
  --json                      Emit raw JSON to stdout.
  --log-level [info|warn|debug]
  -h, --help
```

---

## Implementation notes (brief)

* **Determinism MVP**: enforce lexicographic ordering; record choices in `manifest.environment` and `archive` blocks; optionally allow `--strip-ownership`. Fixed mtimes can be added later if desired.
* **Per-file hashing**: stream per-file SHA256 during walk; store in `files[].sha256`.
* **Progress**: show running counts, bytes, current path; in `--dry-run` show estimated total size and counts post-exclusion.
* **Testing**: golden tests that re-freeze a fixture and compare manifest + archive SHA256; fuzz tests on exclusions; path/Unicode cases.

If you want, I can now generate:

* a tiny **example manifest** (JSON + YAML),
* a **FILELIST.csv** column spec (and gzip writing snippet),
* or a **Typer/Click skeleton** that maps exactly to this help.
