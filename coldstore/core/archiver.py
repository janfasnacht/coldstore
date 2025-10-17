"""Streaming tar+gzip archive builder for coldstore v2.0."""

import hashlib
import logging
import tarfile
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .collectors import collect_environment_metadata, collect_git_metadata
from .manifest import (
    MANIFEST_VERSION,
    ArchiveMetadata,
    ColdstoreManifest,
    EventMetadata,
    MemberCount,
    PerFileHashMetadata,
    SourceMetadata,
    SourceNormalization,
    VerificationMetadata,
    generate_archive_id,
    write_filelist_csv,
    write_sha256_file,
)
from .scanner import FileScanner

logger = logging.getLogger(__name__)

# Default compression level for gzip (0-9, where 9 is best compression)
DEFAULT_COMPRESSION_LEVEL = 6


class ArchiveBuilder:
    """
    Streaming tar+gzip archive builder with deterministic ordering.

    Designed for memory efficiency - streams files to archive without loading
    entire archive into memory. Computes archive-level SHA256 hash during writing.
    Uses deterministic (lexicographic) file ordering for reproducible archives.
    """

    def __init__(
        self,
        output_path: Path,
        compression_level: int = DEFAULT_COMPRESSION_LEVEL,
        compute_sha256: bool = True,
        generate_filelist: bool = True,
        generate_manifest: bool = True,
        event_metadata: Optional[EventMetadata] = None,
    ):
        """
        Initialize archive builder.

        Args:
            output_path: Path where archive will be written
            compression_level: Gzip compression level (0-9, default: 6)
            compute_sha256: Whether to compute SHA256 hash of archive (default: True)
            generate_filelist: Whether to generate FILELIST.csv.gz (default: True)
            generate_manifest: Whether to generate MANIFEST files (default: True)
            event_metadata: Optional event metadata for manifest
                (milestone, notes, etc.)

        Note on Determinism:
            Archives are deterministic when the source state is identical:
            - Same file contents → same file hashes in tar
            - Same mtimes → same tar member metadata
            - Same structure → same archive

            When generate_filelist=True, the FILELIST.csv.gz contains mtimes,
            so changing file mtimes will change the FILELIST hash (correct behavior,
            as mtimes are part of the source state we're capturing).
        """
        self.output_path = Path(output_path)
        self.compression_level = compression_level
        self.compute_sha256 = compute_sha256
        self.generate_filelist = generate_filelist
        self.generate_manifest = generate_manifest

        # Validate and set event metadata
        if event_metadata is not None and not isinstance(
            event_metadata, EventMetadata
        ):
            raise TypeError(
                f"event_metadata must be EventMetadata instance, "
                f"got {type(event_metadata).__name__}"
            )
        self.event_metadata = event_metadata or EventMetadata()

        self.archive_sha256: Optional[str] = None
        self.filelist_sha256: Optional[str] = None
        self.bytes_written = 0

        # Validate compression level
        if not 0 <= compression_level <= 9:
            raise ValueError(f"Compression level must be 0-9, got {compression_level}")

    def create_archive(  # noqa: C901
        self,
        scanner: FileScanner,
        arcname_root: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> dict:
        """
        Create tar.gz archive from scanned files in deterministic order.

        Uses streaming tar creation with constant memory usage. Files are written
        in lexicographic order (from scanner.scan()) for reproducible archives.

        Args:
            scanner: FileScanner instance to get files from
            arcname_root: Root name for files in archive (default: source dir name)
            progress_callback: Optional callback(items_processed, total_items) called
                after each file/directory is added to archive

        Returns:
            Dictionary with archive metadata:
                - path: Path to created archive
                - size_bytes: Archive size in bytes
                - sha256: Archive SHA256 hash (if compute_sha256=True)
                - filelist_sha256: FILELIST.csv.gz SHA256 hash
                    (if generate_filelist=True)
                - files_added: Number of files added
                - dirs_added: Number of directories added
                - file_metadata: List of file metadata dicts
                    (if generate_filelist=True)
        """
        if arcname_root is None:
            arcname_root = scanner.source_root.name

        files_added = 0
        dirs_added = 0
        symlinks_added = 0

        logger.info("Creating archive: %s", self.output_path)

        # Count total items for progress reporting
        total_items = 0
        if progress_callback:
            counts = scanner.count_files()
            total_items = counts["total"]

        # Collect file metadata if generating FILELIST.csv.gz
        file_metadata_list: list[dict] = []

        # Create SHA256 hasher if requested
        sha256_hasher = hashlib.sha256() if self.compute_sha256 else None

        try:
            # Open archive for streaming write with gzip compression
            # Use fileobj wrapper to intercept bytes for SHA256 computation
            with open(self.output_path, "wb") as raw_file:
                # Wrap file object to compute SHA256 while writing
                if sha256_hasher:
                    file_obj = _HashingFileWrapper(raw_file, sha256_hasher)
                else:
                    file_obj = raw_file

                with tarfile.open(
                    fileobj=file_obj,
                    mode="w:gz",
                    format=tarfile.PAX_FORMAT,  # Modern format with better metadata
                    compresslevel=self.compression_level,
                ) as tar:
                    # Add files in deterministic (lexicographic) order
                    for path in scanner.scan():
                        # Compute relative path for archive
                        try:
                            rel_path = path.relative_to(scanner.source_root)
                        except ValueError:
                            logger.warning(
                                "Skipping file outside source root: %s", path
                            )
                            continue

                        arcname = str(Path(arcname_root) / rel_path)

                        try:
                            # Collect file metadata if generating FILELIST
                            if self.generate_filelist:
                                metadata = scanner.collect_file_metadata(path)
                                file_metadata_list.append(metadata)

                            # Add file/directory to archive
                            tar.add(path, arcname=arcname, recursive=False)

                            # Count by type (symlinks, directories, files)
                            if path.is_symlink():
                                symlinks_added += 1
                            elif path.is_dir():
                                dirs_added += 1
                            else:
                                files_added += 1

                            # Report progress after each item added
                            if progress_callback:
                                items_processed = (
                                    files_added + dirs_added + symlinks_added
                                )
                                progress_callback(items_processed, total_items)

                        except OSError as e:
                            logger.warning(
                                "Cannot add %s to archive: %s", path, e
                            )
                            continue

                    # Generate and add COLDSTORE metadata files if requested
                    if self.generate_filelist and file_metadata_list:
                        logger.info(
                            "Generating FILELIST.csv.gz with %d entries",
                            len(file_metadata_list),
                        )

                        # Create FILELIST.csv.gz in temp directory
                        with tempfile.TemporaryDirectory() as tmpdir:
                            filelist_path = Path(tmpdir) / "FILELIST.csv.gz"
                            self.filelist_sha256 = write_filelist_csv(
                                filelist_path,
                                file_metadata_list,
                                compression_level=self.compression_level,
                            )

                            # Add FILELIST.csv.gz to archive at
                            # /COLDSTORE/FILELIST.csv.gz
                            coldstore_dir_name = f"{arcname_root}/COLDSTORE"
                            tar.add(
                                filelist_path,
                                arcname=f"{coldstore_dir_name}/FILELIST.csv.gz",
                            )

                        logger.info(
                            "FILELIST.csv.gz added to archive (hash: %s)",
                            self.filelist_sha256[:16],
                        )

                    # Add MANIFEST.yaml if requested
                    # Note: Archive size and SHA256 cannot be determined until after
                    # the archive is closed, so they are set to None in the embedded
                    # YAML. The JSON sidecar will have the complete values.
                    if self.generate_manifest:
                        logger.info("Generating MANIFEST.yaml for archive")

                        # Generate timestamp and archive ID
                        timestamp_utc = datetime.now(timezone.utc).isoformat().replace(
                            "+00:00", "Z"
                        )
                        archive_id = generate_archive_id(timestamp_utc)

                        # Collect metadata
                        git_metadata = collect_git_metadata(scanner.source_root)
                        env_metadata = collect_environment_metadata()

                        # Create manifest with None for size/hash (not yet known)
                        # JSON sidecar will have actual values after archive is closed
                        manifest = ColdstoreManifest(
                            manifest_version=MANIFEST_VERSION,
                            created_utc=timestamp_utc,
                            id=archive_id,
                            source=SourceMetadata(
                                root=str(scanner.source_root.resolve()),
                                normalization=SourceNormalization(
                                    path_separator="/",
                                    unicode_normalization="NFC",
                                    ordering="lexicographic",
                                    exclude_vcs=scanner.exclude_vcs,
                                ),
                            ),
                            event=self.event_metadata,
                            environment=env_metadata,
                            git=git_metadata,
                            archive=ArchiveMetadata(
                                format="tar+gzip",
                                filename=self.output_path.name,
                                size_bytes=None,  # Will be set in JSON sidecar
                                sha256=None,  # Will be set in JSON sidecar
                                member_count=MemberCount(
                                    files=files_added,
                                    dirs=dirs_added,
                                    symlinks=symlinks_added,
                                ),
                            ),
                            verification=VerificationMetadata(
                                per_file_hash=PerFileHashMetadata(
                                    algorithm="sha256",
                                    manifest_hash_of_filelist=self.filelist_sha256,
                                )
                            ),
                            files=[],
                        )

                        # Write MANIFEST.yaml to temp and add to archive
                        with tempfile.TemporaryDirectory() as tmpdir:
                            yaml_temp_path = Path(tmpdir) / "MANIFEST.yaml"
                            manifest.write_yaml(yaml_temp_path)

                            coldstore_dir_name = f"{arcname_root}/COLDSTORE"
                            tar.add(
                                yaml_temp_path,
                                arcname=f"{coldstore_dir_name}/MANIFEST.yaml",
                            )

                        # Store manifest for later update with actual archive info
                        self._manifest = manifest

                        logger.info("MANIFEST.yaml added to archive")

            # Get final hash
            if sha256_hasher:
                self.archive_sha256 = sha256_hasher.hexdigest()

            # Get archive size
            self.bytes_written = self.output_path.stat().st_size

            logger.info(
                "Archive created: %d files, %d dirs, %d bytes",
                files_added,
                dirs_added,
                self.bytes_written,
            )

            # Write JSON sidecar and .sha256 if manifest was generated
            manifest_json_path = None
            sha256_file_path = None

            if self.generate_manifest:
                logger.info(
                    "Writing MANIFEST.json sidecar with actual archive metadata"
                )

                # Update manifest with actual archive size and hash
                # Note: _manifest MUST exist if generate_manifest=True
                self._manifest.archive.size_bytes = self.bytes_written
                self._manifest.archive.sha256 = self.archive_sha256  # May be None

                # Write JSON sidecar
                manifest_json_path = (
                    self.output_path.parent / f"{self.output_path.name}.MANIFEST.json"
                )
                self._manifest.write_json(manifest_json_path)
                logger.info("MANIFEST.json sidecar written: %s", manifest_json_path)

                # Write .sha256 file if SHA256 was computed
                if self.archive_sha256:
                    sha256_file_path = write_sha256_file(
                        self.output_path, self.archive_sha256
                    )
                    logger.info("SHA256 checksum file written: %s", sha256_file_path)

            result = {
                "path": self.output_path,
                "size_bytes": self.bytes_written,
                "sha256": self.archive_sha256,
                "files_added": files_added,
                "dirs_added": dirs_added,
            }

            # Add FILELIST metadata if generated
            if self.generate_filelist:
                result["filelist_sha256"] = self.filelist_sha256
                result["file_metadata"] = file_metadata_list

            # Add MANIFEST paths if generated
            if self.generate_manifest:
                result["manifest_json_path"] = manifest_json_path
                result["sha256_file_path"] = sha256_file_path

            return result

        except Exception as e:
            logger.error("Failed to create archive: %s", e)
            # Clean up partial archive on failure
            if self.output_path.exists():
                try:
                    self.output_path.unlink()
                except OSError:
                    pass
            raise


class _HashingFileWrapper:
    """
    File wrapper that computes SHA256 hash while writing.

    Wraps a file object and updates a SHA256 hasher with all bytes written.
    Designed specifically for use with tarfile.open() in write mode.

    LIMITATIONS:
        This is a minimal file-like wrapper that only implements the methods
        required by tarfile for sequential write operations:
        - write(data): Write bytes and update hash
        - close(): Close wrapped file
        - __enter__/__exit__: Context manager support

        The following file-like methods are NOT implemented:
        - read(), readline(), readlines() - Not needed for write-only mode
        - seek(), tell() - Not needed for sequential writes
        - flush() - Delegated to underlying file object
        - fileno() - Not needed for tarfile operations

        This wrapper is sufficient for tarfile.open(mode="w:gz") but may not
        work with other file operations that require full file-like interface.
    """

    def __init__(self, file_obj, sha256_hasher):
        """
        Initialize hashing file wrapper.

        Args:
            file_obj: File object to wrap (must support write() and close())
            sha256_hasher: hashlib.sha256() instance to update
        """
        self.file_obj = file_obj
        self.sha256_hasher = sha256_hasher

    def write(self, data: bytes) -> int:
        """Write data and update hash."""
        self.sha256_hasher.update(data)
        return self.file_obj.write(data)

    def close(self):
        """Close wrapped file."""
        if hasattr(self.file_obj, "close"):
            self.file_obj.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit."""
        self.close()
