"""Streaming tar+gzip archive builder for coldstore v2.0."""

import hashlib
import logging
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from .manifest import write_filelist_csv
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
        generate_filelist: bool = False,  # TODO: Change to True once stable
    ):
        """
        Initialize archive builder.

        Args:
            output_path: Path where archive will be written
            compression_level: Gzip compression level (0-9, default: 6)
            compute_sha256: Whether to compute SHA256 hash of archive (default: True)
            generate_filelist: Whether to generate FILELIST.csv.gz (default: False)

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

                            if path.is_dir():
                                dirs_added += 1
                            else:
                                files_added += 1

                            # Report progress after each item added
                            if progress_callback:
                                items_processed = files_added + dirs_added
                                progress_callback(items_processed, total_items)

                        except OSError as e:
                            logger.warning(
                                "Cannot add %s to archive: %s", path, e
                            )
                            continue

                    # Generate and add FILELIST.csv.gz if requested
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
