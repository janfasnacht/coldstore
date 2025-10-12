"""Manifest schema definitions and serialization for coldstore archives."""

import csv
import gzip
import hashlib
import re
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class FileType(str, Enum):
    """File type enumeration."""

    FILE = "file"
    DIR = "dir"
    SYMLINK = "symlink"
    OTHER = "other"


class SourceNormalization(BaseModel):
    """Source path normalization settings."""

    path_separator: str = Field(default="/", description="Path separator used")
    unicode_normalization: str = Field(
        default="NFC", description="Unicode normalization form"
    )
    ordering: str = Field(default="lexicographic", description="File ordering method")
    exclude_vcs: bool = Field(
        default=True, description="Whether VCS directories were excluded"
    )


class SourceMetadata(BaseModel):
    """Source project metadata."""

    root: str = Field(..., description="Absolute path to source root")
    normalization: SourceNormalization = Field(
        default_factory=SourceNormalization, description="Normalization settings"
    )


class EventMetadata(BaseModel):
    """Event metadata for the archive."""

    type: Optional[str] = Field(None, description="Event type (e.g., milestone)")
    name: Optional[str] = Field(None, description="Event name")
    notes: list[str] = Field(
        default_factory=list, description="Free-form descriptions (repeatable)"
    )
    contacts: list[str] = Field(
        default_factory=list, description="Contact information"
    )


class SystemMetadata(BaseModel):
    """System metadata."""

    os: str = Field(..., description="Operating system name")
    os_version: str = Field(..., description="OS version")
    hostname: str = Field(..., description="Hostname")


class ToolsMetadata(BaseModel):
    """Tools and environment metadata."""

    coldstore_version: str = Field(..., description="Coldstore version")
    python_version: str = Field(..., description="Python version")


class EnvironmentMetadata(BaseModel):
    """Environment metadata."""

    system: SystemMetadata
    tools: ToolsMetadata


class GitMetadata(BaseModel):
    """Git repository metadata."""

    present: bool = Field(..., description="Whether git repository was detected")
    commit: Optional[str] = Field(None, description="Current commit hash")
    tag: Optional[str] = Field(None, description="Current tag if any")
    branch: Optional[str] = Field(None, description="Current branch")
    dirty: Optional[bool] = Field(None, description="Whether working tree is dirty")
    remote_origin_url: Optional[str] = Field(
        None, description="Remote origin URL if configured"
    )


class MemberCount(BaseModel):
    """Archive member counts."""

    files: int = Field(..., description="Number of files")
    dirs: int = Field(..., description="Number of directories")
    symlinks: int = Field(default=0, description="Number of symlinks")


class ArchiveMetadata(BaseModel):
    """Archive file metadata."""

    format: str = Field(default="tar+gzip", description="Archive format")
    filename: str = Field(..., description="Archive filename")
    size_bytes: int = Field(..., description="Archive size in bytes")
    sha256: str = Field(..., description="Archive SHA256 checksum")
    member_count: MemberCount = Field(..., description="Member counts by type")

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        """Validate SHA256 is 64 hex characters."""
        if not re.match(r"^[a-fA-F0-9]{64}$", v):
            raise ValueError("SHA256 must be 64 hexadecimal characters")
        return v.lower()  # Normalize to lowercase


class PerFileHashMetadata(BaseModel):
    """Per-file hash verification metadata."""

    algorithm: str = Field(default="sha256", description="Hash algorithm used")
    manifest_hash_of_filelist: Optional[str] = Field(
        None, description="Hash of the FILELIST.csv.gz file"
    )


class VerificationMetadata(BaseModel):
    """Verification metadata."""

    per_file_hash: PerFileHashMetadata = Field(
        default_factory=PerFileHashMetadata, description="Per-file hash metadata"
    )


class FileEntry(BaseModel):
    """Individual file entry in manifest."""

    path: str = Field(..., description="Relative path from source root")
    type: FileType = Field(..., description="File type")
    size: Optional[int] = Field(
        None, description="File size in bytes (None for directories)"
    )
    mode: str = Field(..., description="File mode (octal string)")
    mtime_utc: str = Field(..., description="Last modified time (ISO-8601 UTC)")
    sha256: Optional[str] = Field(None, description="SHA256 hash for files")
    link_target: Optional[str] = Field(None, description="Symlink target if applicable")

    @field_validator("path")
    @classmethod
    def validate_path_is_relative(cls, v: str) -> str:
        """Validate that path is relative, not absolute."""
        from pathlib import Path

        if Path(v).is_absolute():
            raise ValueError(f"Path must be relative, not absolute: {v}")
        return v

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: Optional[str]) -> Optional[str]:
        """Validate SHA256 is 64 hex characters."""
        if v is None:
            return v
        if not re.match(r"^[a-fA-F0-9]{64}$", v):
            raise ValueError("SHA256 must be 64 hexadecimal characters")
        return v.lower()  # Normalize to lowercase

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate mode is valid octal format (0644 not 0o644)."""
        # Accept both "0644" and "0o644" but normalize to "0644"
        if v.startswith("0o"):
            v = v[2:]  # Strip "0o" prefix
        if not re.match(r"^[0-7]{3,4}$", v):
            raise ValueError(f"Mode must be valid octal (e.g. 0644): {v}")
        return v.zfill(4)  # Pad to 4 digits

    # TODO: Add timestamp validation for mtime_utc (ISO-8601 format)
    # TODO: Add helper classmethod: create_from_path(path, stat_result)


class ColdstoreManifest(BaseModel):
    """Complete coldstore manifest schema."""

    manifest_version: str = Field(default="1.0", description="Manifest schema version")
    created_utc: str = Field(..., description="Creation timestamp (ISO-8601 UTC)")
    id: str = Field(..., description="Unique archive identifier")

    source: SourceMetadata
    event: EventMetadata = Field(
        default_factory=EventMetadata, description="Event metadata"
    )
    environment: EnvironmentMetadata
    git: GitMetadata
    archive: ArchiveMetadata
    verification: VerificationMetadata = Field(
        default_factory=VerificationMetadata, description="Verification metadata"
    )
    files: list[FileEntry] = Field(
        default_factory=list, description="File entries (may be truncated)"
    )

    def to_yaml(self) -> str:
        """
        Serialize manifest to YAML string.

        Returns:
            YAML string representation
        """
        # Convert to dict and serialize
        data = self.model_dump(exclude_none=True, mode="json")
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    # TODO: Add write_to_file(path) method for disk I/O
    # TODO: Add add_file(file_entry) helper method

    def to_json(self, indent: int = 2) -> str:
        """
        Serialize manifest to JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string representation
        """
        return self.model_dump_json(exclude_none=True, indent=indent)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "ColdstoreManifest":
        """
        Deserialize manifest from YAML string.

        Args:
            yaml_str: YAML string to parse

        Returns:
            ColdstoreManifest instance
        """
        data = yaml.safe_load(yaml_str)
        return cls(**data)

    # TODO: Add read_from_file(path) classmethod for disk I/O

    @classmethod
    def from_json(cls, json_str: str) -> "ColdstoreManifest":
        """
        Deserialize manifest from JSON string.

        Args:
            json_str: JSON string to parse

        Returns:
            ColdstoreManifest instance
        """
        return cls.model_validate_json(json_str)


# FILELIST.csv.gz schema constants
FILELIST_COLUMNS = [
    "relpath",
    "type",
    "size_bytes",
    "mode_octal",
    "uid",
    "gid",
    "mtime_utc",
    "sha256",
    "link_target",
    "is_executable",
    "ext",
]

FILELIST_DTYPES = {
    "relpath": str,
    "type": str,
    "size_bytes": int,
    "mode_octal": str,
    "uid": int,
    "gid": int,
    "mtime_utc": str,
    "sha256": str,
    "link_target": str,
    "is_executable": int,
    "ext": str,
}

def write_filelist_csv(
    output_path: Path,
    file_entries: list[FileEntry | dict],
    compression_level: int = 6,
) -> str:
    """
    Write file entries to gzipped CSV file with deterministic ordering.

    Args:
        output_path: Path to write FILELIST.csv.gz
        file_entries: List of FileEntry objects or metadata dicts from scanner
        compression_level: Gzip compression level (1-9)

    Returns:
        SHA256 hash of the FILELIST.csv.gz file (hex string)

    Notes:
        - Entries are sorted lexicographically by path for determinism
        - CSV follows FILELIST_COLUMNS schema
        - Empty/None values written as empty strings
        - All paths use POSIX separators (/)
        - Accepts either FileEntry objects or dicts from scanner.collect_file_metadata()
    """
    # Sort entries lexicographically for deterministic output
    sorted_entries = sorted(
        file_entries,
        key=lambda e: e.path if isinstance(e, FileEntry) else e["path"]
    )

    # Write CSV to gzipped file
    # Use GzipFile with mtime=0 for deterministic output (no timestamp in header)
    # filename="" to avoid embedding filename in gzip header (for determinism)
    import io

    with open(output_path, "wb") as f:
        with gzip.GzipFile(
            fileobj=f,
            mode="wb",
            compresslevel=compression_level,
            mtime=0,
            filename="",
        ) as gz:
            # Wrap in TextIOWrapper for text mode
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text_gz:
                writer = csv.DictWriter(text_gz, fieldnames=FILELIST_COLUMNS)
                writer.writeheader()

                for entry in sorted_entries:
                    # Handle both FileEntry objects and dicts from scanner
                    if isinstance(entry, FileEntry):
                        # Extract extension from path
                        ext = (
                            Path(entry.path).suffix.lstrip(".")
                            if Path(entry.path).suffix
                            else ""
                        )

                        # Determine if executable (check user execute bit in mode)
                        mode_int = int(entry.mode, 8)  # Convert octal string to int
                        is_executable = 1 if (mode_int & 0o100) else 0

                        row = {
                            "relpath": entry.path,
                            "type": entry.type.value,
                            "size_bytes": (
                                entry.size if entry.size is not None else ""
                            ),
                            "mode_octal": entry.mode,
                            "uid": "",  # Not available in FileEntry
                            "gid": "",  # Not available in FileEntry
                            "mtime_utc": entry.mtime_utc,
                            "sha256": entry.sha256 if entry.sha256 else "",
                            "link_target": (
                                entry.link_target if entry.link_target else ""
                            ),
                            "is_executable": is_executable,
                            "ext": ext,
                        }
                    else:
                        # Dict from scanner.collect_file_metadata()
                        row = {
                            "relpath": entry["path"],
                            "type": entry["type"].value,
                            "size_bytes": (
                                entry["size"]
                                if entry.get("size") is not None
                                else ""
                            ),
                            "mode_octal": entry["mode"],
                            "uid": entry.get("_uid", ""),
                            "gid": entry.get("_gid", ""),
                            "mtime_utc": entry["mtime_utc"],
                            "sha256": entry.get("sha256", ""),
                            "link_target": entry.get("link_target", ""),
                            "is_executable": 1 if entry.get("_is_executable") else 0,
                            "ext": entry.get("_ext", ""),
                        }
                    writer.writerow(row)

    # Compute SHA256 hash of the output file
    hasher = hashlib.sha256()
    with open(output_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def read_filelist_csv(csv_path: Path) -> list[dict]:
    """
    Read file entries from gzipped CSV file.

    Args:
        csv_path: Path to FILELIST.csv.gz

    Returns:
        List of file entry dictionaries with proper type conversion

    Notes:
        - Converts numeric fields to int
        - Empty strings converted to None for optional fields
        - All paths use POSIX separators (/)
    """
    entries = []

    with gzip.open(csv_path, "rt", newline="") as gz:
        reader = csv.DictReader(gz)

        for row in reader:
            # Type conversions based on FILELIST_DTYPES
            entry = {
                "relpath": row["relpath"],
                "type": row["type"],
                "size_bytes": int(row["size_bytes"]) if row["size_bytes"] else None,
                "mode_octal": row["mode_octal"],
                "uid": int(row["uid"]) if row["uid"] else None,
                "gid": int(row["gid"]) if row["gid"] else None,
                "mtime_utc": row["mtime_utc"],
                "sha256": row["sha256"] if row["sha256"] else None,
                "link_target": row["link_target"] if row["link_target"] else None,
                "is_executable": int(row["is_executable"]),
                "ext": row["ext"] if row["ext"] else None,
            }
            entries.append(entry)

    return entries
