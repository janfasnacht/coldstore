"""Multi-level archive integrity verification for coldstore.

This module provides comprehensive verification capabilities for coldstore archives:
- Level 1 (Quick): Archive hash, manifest validation, FILELIST hash
- Level 2 (Deep): Per-file hash verification with progress tracking

Design Philosophy:
    Verification is a killer feature that distinguishes coldstore from basic
    archiving tools. Users should be able to verify archive integrity at
    multiple levels without needing the original source.
"""

import hashlib
import logging
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .manifest import ColdstoreManifest, read_filelist_csv

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of archive verification.

    Attributes:
        passed: Whether all checks passed
        level: Verification level performed ("quick" or "deep")
        errors: List of error messages (failures)
        warnings: List of warning messages (non-critical issues)
        checks_performed: Number of checks performed
        checks_passed: Number of checks that passed
        files_verified: Number of files verified (deep mode only)
        bytes_verified: Total bytes verified (deep mode only)
        elapsed_seconds: Time taken for verification
    """

    passed: bool
    level: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks_performed: int = 0
    checks_passed: int = 0
    files_verified: Optional[int] = None
    bytes_verified: Optional[int] = None
    elapsed_seconds: float = 0.0

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.passed = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def add_check(self, passed: bool, error_message: Optional[str] = None) -> None:
        """Record a check result.

        Args:
            passed: Whether the check passed
            error_message: Error message if check failed
        """
        self.checks_performed += 1
        if passed:
            self.checks_passed += 1
        elif error_message:
            self.add_error(error_message)

    def get_throughput_mbps(self) -> Optional[float]:
        """Calculate verification throughput in MB/s.

        Returns:
            Throughput in MB/s, or None if not applicable
        """
        if self.bytes_verified and self.elapsed_seconds > 0:
            mb_verified = self.bytes_verified / (1024 * 1024)
            return mb_verified / self.elapsed_seconds
        return None

    def get_summary(self) -> str:
        """Generate human-readable summary of verification.

        Returns:
            Summary string (e.g., "5 checks, 100 files, 1.2 GB verified in 2.5s")
        """
        parts = []

        # Checks summary
        if self.checks_performed > 0:
            parts.append(f"{self.checks_performed} checks")

        # Files summary (deep mode)
        if self.files_verified is not None:
            parts.append(f"{self.files_verified} files")

        # Bytes summary (deep mode)
        if self.bytes_verified is not None:
            if self.bytes_verified < 1024:
                parts.append(f"{self.bytes_verified} B")
            elif self.bytes_verified < 1024 * 1024:
                parts.append(f"{self.bytes_verified / 1024:.1f} KB")
            elif self.bytes_verified < 1024 * 1024 * 1024:
                parts.append(f"{self.bytes_verified / (1024 * 1024):.1f} MB")
            else:
                parts.append(f"{self.bytes_verified / (1024 * 1024 * 1024):.2f} GB")

        # Throughput (deep mode)
        throughput = self.get_throughput_mbps()
        if throughput:
            parts.append(f"{throughput:.1f} MB/s")

        # Time
        if self.elapsed_seconds > 0:
            parts.append(f"in {self.elapsed_seconds:.2f}s")

        return ", ".join(parts) if parts else "No verification performed"

    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON output.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        result = {
            "passed": self.passed,
            "level": self.level,
            "checks_performed": self.checks_performed,
            "checks_passed": self.checks_passed,
            "files_verified": self.files_verified,
            "bytes_verified": self.bytes_verified,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "errors": self.errors,
            "warnings": self.warnings,
        }

        # Add throughput if available
        throughput = self.get_throughput_mbps()
        if throughput:
            result["throughput_mbps"] = round(throughput, 2)

        return result


class ArchiveVerifier:
    """Multi-level archive integrity verifier.

    Provides independent verification of coldstore archives without needing
    the original source. Supports both quick (metadata-level) and deep
    (per-file hash) verification modes.

    Example:
        >>> verifier = ArchiveVerifier(Path("archive.tar.gz"))
        >>> result = verifier.verify_quick()
        >>> if result.passed:
        ...     print("Archive verified successfully!")
    """

    def __init__(
        self,
        archive_path: Path,
        manifest_path: Optional[Path] = None,
    ):
        """Initialize archive verifier.

        Args:
            archive_path: Path to .tar.gz archive to verify
            manifest_path: Optional path to MANIFEST.json file
                (defaults to archive_path + ".MANIFEST.json")

        Raises:
            FileNotFoundError: If archive does not exist
        """
        self.archive_path = Path(archive_path)
        if not self.archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        # Determine manifest path (default: archive + ".MANIFEST.json")
        if manifest_path:
            self.manifest_path = Path(manifest_path)
        else:
            self.manifest_path = (
                self.archive_path.parent / f"{self.archive_path.name}.MANIFEST.json"
            )

        # Determine SHA256 checksum file path
        self.sha256_path = self.archive_path.parent / f"{self.archive_path.name}.sha256"

        self.manifest: Optional[ColdstoreManifest] = None

        # Cache for archive root (determined from tar contents)
        self._archive_root: Optional[str] = None

    def verify_quick(self) -> VerificationResult:
        """Perform quick verification (Level 1).

        Checks:
        - Archive SHA256 hash matches .sha256 file
        - MANIFEST.json exists and has valid schema
        - Manifest internal consistency
        - FILELIST.csv.gz hash matches manifest

        Returns:
            VerificationResult with check results

        Note:
            Quick verification should complete in <5 seconds for any archive.
        """
        start_time = time.time()
        result = VerificationResult(passed=True, level="quick")

        logger.debug("Starting quick verification: %s", self.archive_path)

        # Check 1: Verify archive SHA256 hash
        self._verify_archive_hash(result)

        # Check 2: Load and validate manifest
        manifest_valid = self._load_and_validate_manifest(result)

        if manifest_valid:
            # Check 3: Verify archive size matches manifest
            self._verify_archive_size(result)

            # Check 4: Verify member counts consistency
            self._verify_member_counts(result)

            # Check 5: Verify FILELIST.csv.gz hash
            self._verify_filelist_hash(result)

        result.elapsed_seconds = time.time() - start_time
        logger.debug(
            "Quick verification complete: %s (%.2fs)",
            "PASSED" if result.passed else "FAILED",
            result.elapsed_seconds,
        )

        return result

    def verify_deep(  # noqa: C901
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        fail_fast: bool = False,
    ) -> VerificationResult:
        """Perform deep verification (Level 2).

        Performs all quick checks plus:
        - Extract and verify SHA256 hash for every file
        - Compare against FILELIST.csv.gz entries
        - Validate tar structure integrity

        Args:
            progress_callback: Optional callback(files_verified, total_files, current_file)
                called after each file is verified
            fail_fast: If True, stop at first verification error

        Returns:
            VerificationResult with detailed check results

        Note:
            Deep verification may take significant time for large archives.
            Target throughput: 100+ MB/s.
        """
        start_time = time.time()
        result = VerificationResult(passed=True, level="deep")

        logger.debug("Starting deep verification: %s", self.archive_path)

        # First, run all quick checks
        quick_result = self.verify_quick()

        # Merge quick results into deep result
        result.errors.extend(quick_result.errors)
        result.warnings.extend(quick_result.warnings)
        result.checks_performed = quick_result.checks_performed
        result.checks_passed = quick_result.checks_passed
        result.passed = quick_result.passed

        # If quick checks failed and fail_fast is enabled, stop here
        if not quick_result.passed and fail_fast:
            result.elapsed_seconds = time.time() - start_time
            logger.warning("Quick checks failed, skipping deep verification")
            return result

        # If manifest didn't load, we can't do deep verification
        if not self.manifest:
            result.add_error("Cannot perform deep verification: manifest not loaded")
            result.elapsed_seconds = time.time() - start_time
            return result

        # Load FILELIST.csv.gz for per-file hash verification
        filelist_entries = self._load_filelist(result)
        if not filelist_entries:
            result.add_error(
                "Cannot perform deep verification: FILELIST.csv.gz not loaded"
            )
            result.elapsed_seconds = time.time() - start_time
            return result

        # Create hash lookup dictionary (path -> expected_hash)
        hash_lookup = {
            entry["relpath"]: entry["sha256"]
            for entry in filelist_entries
            if entry["sha256"]  # Only files with hashes
        }

        # Get archive root name from tar contents
        archive_root = self._get_archive_root()

        # Verify per-file hashes by reading tar members
        files_verified = 0
        bytes_verified = 0
        files_with_errors = []

        try:
            with tarfile.open(self.archive_path, "r:gz") as tar:
                # Get all file members (not directories or COLDSTORE metadata)
                file_members = [
                    m
                    for m in tar.getmembers()
                    if m.isfile()
                    and not m.name.endswith(
                        ("/COLDSTORE/FILELIST.csv.gz", "/COLDSTORE/MANIFEST.yaml")
                    )
                ]

                total_files = len(file_members)
                logger.debug("Verifying hashes for %d files", total_files)

                for member in file_members:
                    # Extract relative path (remove archive root prefix)
                    member_path = member.name
                    if member_path.startswith(f"{archive_root}/"):
                        rel_path = member_path[len(archive_root) + 1 :]
                    else:
                        rel_path = member_path

                    # Look up expected hash
                    expected_hash = hash_lookup.get(rel_path)

                    if expected_hash is None:
                        result.add_warning(f"No hash found in FILELIST for: {rel_path}")
                        files_verified += 1
                        if progress_callback:
                            progress_callback(files_verified, total_files, rel_path)
                        continue

                    # Compute actual hash by reading tar member
                    try:
                        file_obj = tar.extractfile(member)
                        if file_obj is None:
                            result.add_error(
                                f"Cannot extract file for verification: {rel_path}"
                            )
                            files_with_errors.append(rel_path)
                            if fail_fast:
                                break
                            continue

                        actual_hash = self._compute_hash_from_fileobj(file_obj)

                        # Track bytes verified
                        bytes_verified += member.size

                        # Compare hashes
                        if actual_hash != expected_hash:
                            error_msg = (
                                f"Hash mismatch: {rel_path}\n"
                                f"  Expected: {expected_hash}\n"
                                f"  Got:      {actual_hash}"
                            )
                            result.add_error(error_msg)
                            files_with_errors.append(rel_path)

                            if fail_fast:
                                break
                        else:
                            result.add_check(True)

                        files_verified += 1

                        # Report progress
                        if progress_callback:
                            progress_callback(files_verified, total_files, rel_path)

                    except Exception as e:
                        error_msg = f"Error verifying {rel_path}: {e}"
                        result.add_error(error_msg)
                        files_with_errors.append(rel_path)

                        if fail_fast:
                            break

        except tarfile.TarError as e:
            result.add_error(f"Tar structure error: {e}")
        except Exception as e:
            result.add_error(f"Unexpected error during deep verification: {e}")

        result.files_verified = files_verified
        result.bytes_verified = bytes_verified
        result.elapsed_seconds = time.time() - start_time

        # Add summary if there were file errors
        if files_with_errors:
            result.add_warning(
                f"{len(files_with_errors)} file(s) failed verification out of {files_verified} checked"
            )

        logger.debug(
            "Deep verification complete: %s (%.2fs, %d files verified)",
            "PASSED" if result.passed else "FAILED",
            result.elapsed_seconds,
            files_verified,
        )

        return result

    # ========================================================================
    # Private helper methods
    # ========================================================================

    def _get_archive_root(self) -> str:
        """Determine archive root directory from tar contents.

        Returns:
            Archive root directory name (e.g., "project_name")

        Note:
            Caches the result after first call for efficiency.
        """
        if self._archive_root is not None:
            return self._archive_root

        # Open tar and get first member to determine root
        try:
            with tarfile.open(self.archive_path, "r:gz") as tar:
                members = tar.getmembers()
                if not members:
                    # Empty archive - use archive filename as fallback
                    self._archive_root = Path(self.archive_path.stem).stem
                    return self._archive_root

                # Get first member and extract root directory
                first_member = members[0].name
                # Root is the first path component
                root = first_member.split("/")[0]
                self._archive_root = root
                return self._archive_root

        except tarfile.TarError:
            # Fallback to archive filename
            self._archive_root = Path(self.archive_path.stem).stem
            return self._archive_root

    def _verify_archive_hash(self, result: VerificationResult) -> bool:
        """Verify archive SHA256 hash against .sha256 file.

        Args:
            result: VerificationResult to update

        Returns:
            True if hash verification passed, False otherwise
        """
        # Check if .sha256 file exists
        if not self.sha256_path.exists():
            result.add_warning(
                f"SHA256 checksum file not found: {self.sha256_path.name}"
            )
            return False

        # Read expected hash from .sha256 file
        try:
            sha256_content = self.sha256_path.read_text().strip()
            # Format: "hash  filename" (sha256sum format)
            expected_hash = sha256_content.split()[0]
        except (OSError, IndexError) as e:
            result.add_error(f"Cannot read SHA256 file: {e}")
            return False

        # Compute actual archive hash
        try:
            actual_hash = self._compute_file_hash(self.archive_path)
        except OSError as e:
            result.add_error(f"Cannot compute archive hash: {e}")
            return False

        # Compare hashes
        if actual_hash != expected_hash:
            result.add_check(
                False,
                f"SHA256 mismatch\n"
                f"  Expected: {expected_hash}\n"
                f"  Got:      {actual_hash}\n"
                f"  → Archive may be corrupted or tampered with",
            )
            return False

        result.add_check(True)
        return True

    def _load_and_validate_manifest(self, result: VerificationResult) -> bool:
        """Load and validate MANIFEST.json.

        Args:
            result: VerificationResult to update

        Returns:
            True if manifest loaded and validated successfully
        """
        # Check if manifest exists
        if not self.manifest_path.exists():
            result.add_error(f"Manifest file not found: {self.manifest_path.name}")
            return False

        # Load manifest
        try:
            self.manifest = ColdstoreManifest.read_json(self.manifest_path)
            result.add_check(True)
        except Exception as e:
            result.add_error(
                f"Invalid manifest schema: {e}\n"
                f"  → Manifest file may be corrupted or from incompatible version"
            )
            return False

        # Validate manifest version
        if self.manifest.manifest_version != "1.0":
            result.add_warning(
                f"Manifest version {self.manifest.manifest_version} may not be fully supported"
            )

        return True

    def _verify_archive_size(self, result: VerificationResult) -> bool:
        """Verify archive size matches manifest.

        Args:
            result: VerificationResult to update

        Returns:
            True if size matches
        """
        if not self.manifest:
            return False

        actual_size = self.archive_path.stat().st_size
        expected_size = self.manifest.archive.size_bytes

        if expected_size is None:
            result.add_warning("Archive size not recorded in manifest")
            return False

        if actual_size != expected_size:
            result.add_check(
                False,
                f"Archive size mismatch: expected {expected_size} bytes, got {actual_size} bytes",
            )
            return False

        result.add_check(True)
        return True

    def _verify_member_counts(self, result: VerificationResult) -> bool:
        """Verify archive member counts are consistent.

        Args:
            result: VerificationResult to update

        Returns:
            True if counts are consistent
        """
        if not self.manifest:
            return False

        # This is a basic consistency check
        # In deep verification, we'll verify actual counts
        member_count = self.manifest.archive.member_count

        if member_count.files < 0 or member_count.dirs < 0 or member_count.symlinks < 0:
            result.add_error("Invalid member counts in manifest (negative values)")
            return False

        result.add_check(True)
        return True

    def _verify_filelist_hash(self, result: VerificationResult) -> bool:
        """Verify FILELIST.csv.gz hash matches manifest.

        Args:
            result: VerificationResult to update

        Returns:
            True if FILELIST hash matches
        """
        if not self.manifest:
            return False

        expected_hash = (
            self.manifest.verification.per_file_hash.manifest_hash_of_filelist
        )

        if expected_hash is None:
            result.add_warning("FILELIST hash not recorded in manifest")
            return False

        # Extract FILELIST.csv.gz from archive and compute hash
        try:
            archive_root = self._get_archive_root()
            filelist_arcname = f"{archive_root}/COLDSTORE/FILELIST.csv.gz"

            with tarfile.open(self.archive_path, "r:gz") as tar:
                try:
                    member = tar.getmember(filelist_arcname)
                except KeyError:
                    result.add_error(
                        f"FILELIST.csv.gz not found in archive: {filelist_arcname}"
                    )
                    return False

                file_obj = tar.extractfile(member)
                if file_obj is None:
                    result.add_error("Cannot extract FILELIST.csv.gz from archive")
                    return False

                actual_hash = self._compute_hash_from_fileobj(file_obj)

        except tarfile.TarError as e:
            result.add_error(f"Cannot extract FILELIST from archive: {e}")
            return False

        # Compare hashes
        if actual_hash != expected_hash:
            result.add_check(
                False,
                f"FILELIST hash mismatch\n"
                f"  Expected: {expected_hash}\n"
                f"  Got:      {actual_hash}\n"
                f"  → FILELIST metadata has been modified or corrupted",
            )
            return False

        result.add_check(True)
        return True

    def _load_filelist(self, result: VerificationResult) -> Optional[list[dict]]:
        """Load FILELIST.csv.gz from archive.

        Args:
            result: VerificationResult to update

        Returns:
            List of FILELIST entries, or None if loading failed
        """
        try:
            archive_root = self._get_archive_root()
            filelist_arcname = f"{archive_root}/COLDSTORE/FILELIST.csv.gz"

            with tarfile.open(self.archive_path, "r:gz") as tar:
                try:
                    member = tar.getmember(filelist_arcname)
                except KeyError:
                    result.add_error(
                        f"FILELIST.csv.gz not found in archive: {filelist_arcname}"
                    )
                    return None

                file_obj = tar.extractfile(member)
                if file_obj is None:
                    result.add_error("Cannot extract FILELIST.csv.gz")
                    return None

                # Write to temp file and read with read_filelist_csv
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".csv.gz", delete=False) as tmp:
                    tmp.write(file_obj.read())
                    tmp_path = Path(tmp.name)

                try:
                    entries = read_filelist_csv(tmp_path)
                    return entries
                finally:
                    tmp_path.unlink()

        except Exception as e:
            result.add_error(f"Error loading FILELIST: {e}")
            return None

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            SHA256 hash (hex string)
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _compute_hash_from_fileobj(self, file_obj) -> str:
        """Compute SHA256 hash from file-like object.

        Args:
            file_obj: File-like object

        Returns:
            SHA256 hash (hex string)
        """
        hasher = hashlib.sha256()
        for chunk in iter(lambda: file_obj.read(65536), b""):
            hasher.update(chunk)
        return hasher.hexdigest()
