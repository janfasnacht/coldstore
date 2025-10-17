"""Archive inspection and analysis for coldstore.

This module provides comprehensive archive inspection capabilities without
requiring extraction. Users can explore archive contents, analyze file
distributions, and extract metadata quickly.
"""

import logging
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

from .manifest import ColdstoreManifest, read_filelist_csv

logger = logging.getLogger(__name__)


class ArchiveInspector:
    """Inspect and analyze coldstore archives without extraction.

    Provides quick insights into archive contents by reading embedded metadata
    (MANIFEST.yaml, FILELIST.csv.gz) and analyzing archive structure.

    Example:
        >>> inspector = ArchiveInspector(Path("archive.tar.gz"))
        >>> summary = inspector.summary()
        >>> print(summary['archive']['filename'])
    """

    def __init__(self, archive_path: Path):
        """Initialize archive inspector.

        Args:
            archive_path: Path to .tar.gz archive to inspect

        Raises:
            FileNotFoundError: If archive does not exist
        """
        self.archive_path = Path(archive_path)
        if not self.archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        # Determine manifest path (sidecar JSON)
        self.manifest_path = (
            self.archive_path.parent / f"{self.archive_path.name}.MANIFEST.json"
        )

        # Lazy-loaded attributes
        self._manifest: Optional[ColdstoreManifest] = None
        self._filelist: Optional[list[dict]] = None
        self._archive_root: Optional[str] = None

    @property
    def manifest(self) -> Optional[ColdstoreManifest]:
        """Get manifest (lazy-loaded).

        Returns:
            ColdstoreManifest instance or None if not available
        """
        if self._manifest is None:
            self._manifest = self._load_manifest()
        return self._manifest

    @property
    def filelist(self) -> Optional[list[dict]]:
        """Get filelist entries (lazy-loaded).

        Returns:
            List of file entry dicts or None if not available
        """
        if self._filelist is None:
            self._filelist = self._load_filelist()
        return self._filelist

    def summary(self) -> dict:
        """Generate high-level archive summary.

        Returns:
            Dictionary with archive overview:
                - archive: Archive metadata (filename, size, created, id)
                - contents: Content summary (file counts, sizes)
                - source: Source project info (path, git state)
                - event: Event metadata (milestone, notes)
                - environment: Environment info (OS, hostname, tools)
                - integrity: Integrity info (hashes)
                - compression: Compression ratio info (if available)
        """
        summary_data = {}

        # Archive basic info
        archive_stat = self.archive_path.stat()
        compressed_size = archive_stat.st_size

        summary_data["archive"] = {
            "filename": self.archive_path.name,
            "size_bytes": compressed_size,
            "path": str(self.archive_path),
        }

        # If manifest exists, add rich metadata
        if self.manifest:
            summary_data["archive"].update(
                {
                    "created_utc": self.manifest.created_utc,
                    "id": self.manifest.id,
                }
            )

            # Contents summary from manifest
            member_count = self.manifest.archive.member_count
            summary_data["contents"] = {
                "files": member_count.files,
                "directories": member_count.dirs,
                "symlinks": member_count.symlinks,
                "total_size_bytes": (
                    self.manifest.archive.size_bytes
                    if self.manifest.archive.size_bytes
                    else archive_stat.st_size
                ),
            }

            # Source metadata
            summary_data["source"] = {
                "root": self.manifest.source.root,
                "normalization": {
                    "path_separator": self.manifest.source.normalization.path_separator,
                    "ordering": self.manifest.source.normalization.ordering,
                    "exclude_vcs": self.manifest.source.normalization.exclude_vcs,
                },
            }

            # Git metadata (if present)
            if self.manifest.git.present:
                git_data = {
                    "present": True,
                    "commit": self.manifest.git.commit,
                    "branch": self.manifest.git.branch,
                    "tag": self.manifest.git.tag,
                    "dirty": self.manifest.git.dirty,
                }
                if self.manifest.git.remote_origin_url:
                    git_data["remote_url"] = self.manifest.git.remote_origin_url
                summary_data["source"]["git"] = git_data
            else:
                summary_data["source"]["git"] = {"present": False}

            # Event metadata
            event = self.manifest.event
            if event.type or event.name or event.notes or event.contacts:
                summary_data["event"] = {
                    "type": event.type,
                    "name": event.name,
                    "notes": event.notes,
                    "contacts": event.contacts,
                }

            # Environment metadata
            summary_data["environment"] = {
                "system": {
                    "os": self.manifest.environment.system.os,
                    "os_version": self.manifest.environment.system.os_version,
                    "hostname": self.manifest.environment.system.hostname,
                },
                "tools": {
                    "coldstore_version": (
                        self.manifest.environment.tools.coldstore_version
                    ),
                    "python_version": self.manifest.environment.tools.python_version,
                },
            }

            # Integrity metadata
            summary_data["integrity"] = {
                "archive_sha256": self.manifest.archive.sha256,
                "filelist_sha256": (
                    self.manifest.verification.per_file_hash.manifest_hash_of_filelist
                ),
            }

            # Compression ratio (if filelist available)
            if self.filelist:
                uncompressed_size = self._calculate_uncompressed_size()
                if uncompressed_size > 0:
                    ratio = (
                        (uncompressed_size - compressed_size) / uncompressed_size * 100
                    )
                    summary_data["compression"] = {
                        "compressed_bytes": compressed_size,
                        "uncompressed_bytes": uncompressed_size,
                        "ratio_percent": round(ratio, 1),
                        "space_saved_bytes": uncompressed_size - compressed_size,
                    }

        else:
            # Minimal info without manifest
            logger.warning(
                "Manifest not found, showing limited information. "
                "To create archives with full metadata, use: "
                "coldstore freeze <source> <destination>"
            )
            summary_data["contents"] = {
                "message": "Manifest not available - limited information"
            }

        return summary_data

    def file_listing(  # noqa: C901
        self,
        pattern: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Get detailed file listing with optional filtering.

        Args:
            pattern: Glob pattern to filter files (e.g., "*.py")
            min_size: Minimum file size in bytes
            max_size: Maximum file size in bytes
            limit: Maximum number of entries to return

        Returns:
            List of file entry dictionaries with keys:
                - relpath: Relative path
                - type: File type (file/dir/symlink)
                - size_bytes: Size in bytes
                - mtime_utc: Modification time
                - sha256: SHA256 hash (for files)
                - link_target: Link target (for symlinks)
        """
        if not self.filelist:
            logger.warning(
                "FILELIST not available. "
                "Create archives with metadata using: "
                "coldstore freeze --filelist <source> <destination>"
            )
            return []

        files = []
        for entry in self.filelist:
            # Apply pattern filter
            if pattern:
                from fnmatch import fnmatch

                if not fnmatch(entry["relpath"], pattern):
                    continue

            # Apply size filters (only for files)
            if entry["type"] == "file":
                size = entry.get("size_bytes")
                if size is not None:
                    if min_size is not None and size < min_size:
                        continue
                    if max_size is not None and size > max_size:
                        continue

            # Build output entry
            file_entry = {
                "relpath": entry["relpath"],
                "type": entry["type"],
                "size_bytes": entry.get("size_bytes"),
                "mtime_utc": entry.get("mtime_utc"),
                "sha256": entry.get("sha256"),
            }

            # Add link target for symlinks
            if entry.get("link_target"):
                file_entry["link_target"] = entry["link_target"]

            files.append(file_entry)

            # Check limit
            if limit is not None and len(files) >= limit:
                break

        return files

    def largest_files(self, n: int = 10) -> list[dict]:
        """Get N largest files from archive.

        Args:
            n: Number of largest files to return (default: 10)

        Returns:
            List of file entries sorted by size (largest first)
            with keys: relpath, size_bytes, size_human
        """
        if not self.filelist:
            logger.warning(
                "FILELIST not available. "
                "Create archives with file metadata using: "
                "coldstore freeze <source> <destination>"
            )
            return []

        # Filter to files only (not directories)
        files = [
            entry
            for entry in self.filelist
            if entry["type"] == "file" and entry.get("size_bytes") is not None
        ]

        # Sort by size descending
        files.sort(key=lambda x: x["size_bytes"], reverse=True)

        # Take top N
        largest = files[:n]

        # Format output
        result = []
        for entry in largest:
            result.append(
                {
                    "relpath": entry["relpath"],
                    "size_bytes": entry["size_bytes"],
                }
            )

        return result

    def statistics(self) -> dict:  # noqa: C901
        """Compute detailed statistics about archive contents.

        Returns:
            Dictionary with detailed stats:
                - file_types: File type distribution
                - size_distribution: Size bucket distribution
                - directory_sizes: Size by directory
        """
        if not self.filelist:
            logger.warning(
                "FILELIST not available. "
                "Statistics require per-file metadata. "
                "Create archives with: coldstore freeze <source> <destination>"
            )
            return {}

        # File type distribution
        file_types = {}
        for entry in self.filelist:
            if entry["type"] == "file":
                ext = entry.get("ext") or "(no extension)"
                if ext not in file_types:
                    file_types[ext] = {"count": 0, "size_bytes": 0}
                file_types[ext]["count"] += 1
                file_types[ext]["size_bytes"] += entry.get("size_bytes", 0)

        # Size distribution buckets
        size_buckets = {
            "< 1 KB": 0,
            "1-100 KB": 0,
            "100KB-1MB": 0,
            "1-10 MB": 0,
            "10-100 MB": 0,
            "> 100 MB": 0,
        }

        for entry in self.filelist:
            if entry["type"] == "file":
                size = entry.get("size_bytes", 0)
                if size < 1024:
                    size_buckets["< 1 KB"] += 1
                elif size < 100 * 1024:
                    size_buckets["1-100 KB"] += 1
                elif size < 1024 * 1024:
                    size_buckets["100KB-1MB"] += 1
                elif size < 10 * 1024 * 1024:
                    size_buckets["1-10 MB"] += 1
                elif size < 100 * 1024 * 1024:
                    size_buckets["10-100 MB"] += 1
                else:
                    size_buckets["> 100 MB"] += 1

        # Directory sizes
        dir_sizes = {}
        for entry in self.filelist:
            if entry["type"] == "file":
                path_parts = entry["relpath"].split("/")
                if len(path_parts) > 1:
                    top_dir = path_parts[0]
                    if top_dir not in dir_sizes:
                        dir_sizes[top_dir] = 0
                    dir_sizes[top_dir] += entry.get("size_bytes", 0)

        # Sort directories by size
        dir_sizes_sorted = sorted(
            dir_sizes.items(), key=lambda x: x[1], reverse=True
        )

        return {
            "file_types": file_types,
            "size_distribution": size_buckets,
            "directory_sizes": dict(dir_sizes_sorted[:10]),  # Top 10 directories
        }

    # ========================================================================
    # Private helper methods
    # ========================================================================

    def _calculate_uncompressed_size(self) -> int:
        """Calculate total uncompressed size from filelist.

        Returns:
            Total size in bytes of all files in archive (uncompressed)
        """
        if not self.filelist:
            return 0

        total_size = 0
        for entry in self.filelist:
            if entry["type"] == "file" and entry.get("size_bytes") is not None:
                total_size += entry["size_bytes"]

        return total_size

    def _load_manifest(self) -> Optional[ColdstoreManifest]:
        """Load manifest from sidecar JSON or embedded YAML.

        Returns:
            ColdstoreManifest instance or None if not found
        """
        # Try sidecar JSON first
        if self.manifest_path.exists():
            try:
                logger.debug("Loading manifest from sidecar: %s", self.manifest_path)
                return ColdstoreManifest.read_json(self.manifest_path)
            except Exception as e:
                logger.warning("Failed to load sidecar manifest: %s", e)

        # Fall back to embedded YAML
        try:
            logger.debug("Attempting to load embedded MANIFEST.yaml")
            return self._extract_embedded_manifest()
        except Exception as e:
            logger.warning("Failed to load embedded manifest: %s", e)
            return None

    def _extract_embedded_manifest(self) -> Optional[ColdstoreManifest]:
        """Extract and parse embedded MANIFEST.yaml from archive.

        Returns:
            ColdstoreManifest instance or None if not found
        """
        try:
            archive_root = self._get_archive_root()
            manifest_arcname = f"{archive_root}/COLDSTORE/MANIFEST.yaml"

            with tarfile.open(self.archive_path, "r:gz") as tar:
                try:
                    member = tar.getmember(manifest_arcname)
                except KeyError:
                    logger.debug("MANIFEST.yaml not found in archive")
                    return None

                file_obj = tar.extractfile(member)
                if file_obj is None:
                    return None

                yaml_content = file_obj.read().decode("utf-8")
                return ColdstoreManifest.from_yaml(yaml_content)

        except Exception as e:
            logger.warning("Error extracting embedded manifest: %s", e)
            return None

    def _load_filelist(self) -> Optional[list[dict]]:
        """Load FILELIST.csv.gz from archive.

        Returns:
            List of file entry dicts or None if not found
        """
        try:
            archive_root = self._get_archive_root()
            filelist_arcname = f"{archive_root}/COLDSTORE/FILELIST.csv.gz"

            with tarfile.open(self.archive_path, "r:gz") as tar:
                try:
                    member = tar.getmember(filelist_arcname)
                except KeyError:
                    logger.debug("FILELIST.csv.gz not found in archive")
                    return None

                file_obj = tar.extractfile(member)
                if file_obj is None:
                    return None

                # Write to temp file and read with read_filelist_csv
                with tempfile.NamedTemporaryFile(
                    suffix=".csv.gz", delete=False
                ) as tmp:
                    tmp.write(file_obj.read())
                    tmp_path = Path(tmp.name)

                try:
                    entries = read_filelist_csv(tmp_path)
                    logger.debug("Loaded %d entries from FILELIST", len(entries))
                    return entries
                finally:
                    tmp_path.unlink()

        except Exception as e:
            logger.warning("Error loading FILELIST: %s", e)
            return None

    def _get_archive_root(self) -> str:
        """Determine archive root directory from tar contents.

        Returns:
            Archive root directory name

        Note:
            Caches the result after first call for efficiency.
        """
        if self._archive_root is not None:
            return self._archive_root

        try:
            with tarfile.open(self.archive_path, "r:gz") as tar:
                members = tar.getmembers()
                if not members:
                    # Empty archive - use archive filename as fallback
                    self._archive_root = Path(self.archive_path.stem).stem
                    return self._archive_root

                # Get first member and extract root directory
                first_member = members[0].name
                root = first_member.split("/")[0]
                self._archive_root = root
                return self._archive_root

        except tarfile.TarError:
            # Fallback to archive filename
            self._archive_root = Path(self.archive_path.stem).stem
            return self._archive_root
