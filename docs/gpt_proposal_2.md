Love it—totally agree with your instinct.

# 1) `gitignore` default & VCS handling (recommended policy)

**Default: do *not* respect `.gitignore`.**
Coldstore’s job is definitive capture—including data/outputs that are usually git-ignored. Make this explicit:

* **`--no-respect-gitignore` (default)**: include everything except VCS control dirs by default.
* **`--respect-gitignore`**: opt-in if someone truly wants a “source-only” style snapshot.

**VCS directories**

* **Exclude by default**: `.git/`, `.hg/`, `.svn/` (they’re huge, not needed for the record).
* **Opt-in to include**: `--include-vcs-metadata` if a user truly wants the whole `.git/` history frozen.

**Git metadata capture (even when excluding `.git/`)**

* Always collect **repo state**: commit SHA, tag, branch, dirty flag, remote origin, and short `git status --porcelain` summary counts (M/A/D/U).
* Optionally (behind a flag like `--git-per-file`), include **per-file git status** columns in `FILELIST.csv` (tracked/untracked/ignored/LFS pointer detection). This is expensive; keep it off by default.

**UX niceties**

* In `--dry-run`, clearly list “files included despite .gitignore” and “VCS dirs excluded by default,” so users see what the policy does.

---

# 2) `FILELIST.csv` column spec (+ deterministic gzip writer)

## Column spec (wide but stable; unambiguous types)

| Column          | Type                | Description                                                                                |
| --------------- | ------------------- | ------------------------------------------------------------------------------------------ |
| `relpath`       | string              | POSIX-style path relative to source root, NFC-normalized; no leading “./”.                 |
| `type`          | enum                | `file` | `dir` | `symlink` | `other`.                                                      |
| `size_bytes`    | int or empty        | File byte size (empty for non-files).                                                      |
| `mode_octal`    | string              | File mode as zero-padded octal (e.g., `0644`, `0755`).                                     |
| `uid`           | int                 | Numeric uid captured (or `0` if stripped).                                                 |
| `gid`           | int                 | Numeric gid captured (or `0` if stripped).                                                 |
| `mtime_utc`     | ISO-8601 string     | Last-modified timestamp in UTC (e.g., `2025-09-28T20:57:01Z`).                             |
| `sha256`        | hex string or empty | Per-file SHA256 of content; empty for dirs/other. (For symlinks: empty—see `link_target`.) |
| `link_target`   | string or empty     | For `symlink`, the link target path as stored; empty otherwise.                            |
| `is_executable` | 0/1                 | Heuristic: true if any execute bit set on a regular file.                                  |
| `ext`           | string              | Lowercased file extension including dot (e.g., `.py`), empty if none.                      |
| `git_tracked`   | 0/1/empty           | If `--git-per-file`: 1 tracked, 0 untracked; empty if repo absent.                         |
| `git_status`    | enum or empty       | If `--git-per-file`: `M`/`A`/`D`/`U`/`CLEAN`/`IGNORED`/`NA`; empty if repo absent.         |
| `lfs_pointer`   | 0/1/empty           | If LFS pointer detection enabled: 1 if pointer file, else 0; empty if not checked.         |

**Conventions**

* Booleans as **0/1** to avoid CSV truthiness ambiguity.
* Nulls as **empty strings**.
* **Ordering**: rows sorted lexicographically by `relpath`.
* **CSV dialect**: comma-separated, header row, UTF-8, RFC4180-friendly (quote as needed).
* **Determinism**: consistent column order, newline `\n`, and gzip *mtime* fixed to zero.

## Gzipped writer (deterministic) + manifest hash

Below is a **drop-in snippet** that:

* Streams rows to a gzipped CSV with **gzip header mtime=0** (deterministic).
* Computes a **SHA256** of the **gzipped bytes** (recommended for `verification.manifest_hash_of_filelist` to avoid OS newline differences).
* Uses **POSIX newlines** and **stable field order**.

```python
import csv
import gzip
import io
import os
import hashlib
from typing import Iterable, Dict

FILELIST_FIELDS = [
    "relpath", "type", "size_bytes", "mode_octal", "uid", "gid",
    "mtime_utc", "sha256", "link_target", "is_executable", "ext",
    "git_tracked", "git_status", "lfs_pointer",
]

def write_filelist_csv_gz(
    rows: Iterable[Dict[str, str]],
    out_path: str,
) -> str:
    """
    Write FILELIST.csv.gz deterministically and return SHA256 of gzipped bytes.
    - rows: iterable of dicts containing exactly FILELIST_FIELDS
    - out_path: destination path for the gzipped CSV
    """
    sha = hashlib.sha256()

    # Ensure parent dir exists
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Open gz file with fixed mtime=0 for deterministic gzip headers
    with open(out_path, "wb") as raw_f:
        with gzip.GzipFile(filename=os.path.basename(out_path), mode="wb", mtime=0, fileobj=raw_f) as gz_f:
            # Wrap in text mode with explicit newline to avoid \r\n on Windows
            text_f = io.TextIOWrapper(gz_f, encoding="utf-8", newline="\n")
            writer = csv.DictWriter(text_f, fieldnames=FILELIST_FIELDS, lineterminator="\n")
            writer.writeheader()

            # IMPORTANT: rows should already be lexicographically sorted by relpath
            for row in rows:
                # Normalize empty/None fields to "", ints to str explicitly
                normalized = {}
                for k in FILELIST_FIELDS:
                    v = row.get(k, "")
                    if v is None:
                        v = ""
                    elif isinstance(v, bool):
                        v = "1" if v else "0"
                    elif isinstance(v, int):
                        v = str(v)
                    normalized[k] = v
                writer.writerow(normalized)

            # Flush text buffer to push all bytes into gz_f
            text_f.flush()
            # At this point data is in gz_f (and raw_f). To compute SHA256, re-open the file.
        # Close gzip writer before hashing
    # Hash the final gzipped file bytes (stable)
    with open(out_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()
```

### How to prepare `rows` (canonicalization checklist)

Before calling `write_filelist_csv_gz`, make sure you:

* **Sort** entries: `rows = sorted(rows, key=lambda r: r["relpath"])`
* **Normalize paths**: ensure `relpath` uses `/` separators and NFC Unicode.
* **Encode types**: `type` in {`file`,`dir`,`symlink`,`other`}; `size_bytes` only for files.
* **Permissions**: `mode_octal` as zero-padded 4-digit string (or 5–6 digits on some systems), e.g. `0644`.
* **Times**: `mtime_utc` as `YYYY-MM-DDTHH:MM:SSZ` (no subseconds).
* **Hashes**: `sha256` should be the content hash for files; empty otherwise.
* **Git columns**: fill only if you enabled per-file git checks; else empty.
* **Booleans**: convert to `0/1` strings.

### Putting the hash into the manifest

* Store the return value as `verification.manifest_hash_of_filelist`.
* Name the file exactly `COLDSTORE/FILELIST.csv.gz` inside the tar so readers can rely on it.

---

If you want, I can also stub:

* a tiny helper `collect_file_entry(path)` that returns a row dict (including mode/uid/gid/mtime extraction and SHA256 streaming),
* or a mini `--dry-run` estimator that walks the tree with exclusions and prints a summary table.
