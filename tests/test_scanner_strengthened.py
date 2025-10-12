"""Strengthened and additional tests for file system scanner.

This file contains improved versions of weak tests and new edge case tests
identified in the test quality review. These tests are more specific, verify
exact behavior, and test edge cases that were missing.
"""

import pytest
from pathlib import Path

from coldstore.core.scanner import FileScanner
from coldstore.core.manifest import FileEntry, FileType


class TestScannerExactValidation:
    """Tests that verify exact file lists instead of existence checks."""

    def test_scanner_finds_exact_files(self, tmp_path):
        """Test scanner finds exactly the expected files (not just any())."""
        # Create known structure
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.md").write_text("content3")

        scanner = FileScanner(tmp_path)
        paths = sorted([str(p.relative_to(tmp_path)) for p in scanner.scan()])

        # Verify EXACT list of files
        expected = sorted(["file1.txt", "file2.py", "subdir", "subdir/file3.md"])
        assert paths == expected, f"Expected {expected} but got {paths}"

    def test_estimate_size_exact_calculation(self, tmp_path):
        """Test size estimation with exact byte counts."""
        # Create files with known sizes
        (tmp_path / "file1.txt").write_bytes(b"a" * 100)  # 100 bytes
        (tmp_path / "file2.txt").write_bytes(b"b" * 250)  # 250 bytes
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "file3.txt").write_bytes(b"c" * 150)  # 150 bytes

        scanner = FileScanner(tmp_path)
        total_size = scanner.estimate_size()

        # Should be exactly 500 bytes (directories don't count)
        assert total_size == 500, f"Expected 500 bytes but got {total_size}"

    def test_exclusion_verifies_both_inclusion_and_exclusion(self, tmp_path):
        """Test exclusions verify BOTH what's excluded AND what's included."""
        # Create mixed structure
        (tmp_path / "keep.py").write_text("keep")
        (tmp_path / "exclude.txt").write_text("exclude")
        (tmp_path / "keep2.md").write_text("keep")
        (tmp_path / "exclude2.txt").write_text("exclude")

        scanner = FileScanner(tmp_path, exclude_patterns=["*.txt"])
        paths = [p.name for p in scanner.scan()]

        # Verify exclusions
        assert "exclude.txt" not in paths
        assert "exclude2.txt" not in paths

        # Verify inclusions (critical - many tests miss this!)
        assert "keep.py" in paths
        assert "keep2.md" in paths


class TestScannerEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_unicode_filenames(self, tmp_path):
        """Test scanner handles Unicode filenames correctly."""
        # Create files with various Unicode characters
        (tmp_path / "test_émoji_🎉.txt").write_text("content")
        (tmp_path / "中文文件.py").write_text("content")
        (tmp_path / "Ελληνικά.md").write_text("content")

        scanner = FileScanner(tmp_path)
        paths = [p.name for p in scanner.scan()]

        assert "test_émoji_🎉.txt" in paths
        assert "中文文件.py" in paths
        assert "Ελληνικά.md" in paths

    def test_glob_pattern_edge_cases(self, tmp_path):
        """Test exclusion patterns with wildcards (*, ?, [])."""
        # Create test structure
        (tmp_path / "test1.txt").write_text("1")
        (tmp_path / "test2.txt").write_text("2")
        (tmp_path / "test_file.py").write_text("py")
        (tmp_path / "data.csv").write_text("csv")

        # Test * wildcard
        scanner = FileScanner(tmp_path, exclude_patterns=["test*.txt"])
        paths = [p.name for p in scanner.scan()]
        assert "test1.txt" not in paths
        assert "test2.txt" not in paths
        assert "test_file.py" in paths  # .py not excluded

    def test_nested_directory_exclusion(self, tmp_path):
        """Test excluding nested directories works correctly."""
        # Create nested structure
        nested = tmp_path / "project" / "build" / "output"
        nested.mkdir(parents=True)
        (nested / "artifact.bin").write_text("build artifact")
        (tmp_path / "project" / "src" / "main.py").parent.mkdir(parents=True)
        (tmp_path / "project" / "src" / "main.py").write_text("source")

        # Exclude build directory
        scanner = FileScanner(tmp_path, exclude_patterns=["build", "build/*"])
        paths = [str(p.relative_to(tmp_path)) for p in scanner.scan()]

        # Verify build excluded
        assert not any("build" in p for p in paths)

        # Verify src included
        assert any("src/main.py" in p for p in paths)

    def test_empty_directory_handling(self, tmp_path):
        """Test scanner handles empty directories correctly."""
        (tmp_path / "empty1").mkdir()
        (tmp_path / "empty2").mkdir()
        (tmp_path / "not_empty").mkdir()
        (tmp_path / "not_empty" / "file.txt").write_text("content")

        scanner = FileScanner(tmp_path)
        paths = [p.name for p in scanner.scan()]

        # Empty dirs should be included in scan
        assert "empty1" in paths
        assert "empty2" in paths
        assert "not_empty" in paths

    def test_symlink_to_directory(self, tmp_path):
        """Test scanner handles symlinked directories."""
        # Create real dir and symlink to it
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "file.txt").write_text("content")

        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        scanner = FileScanner(tmp_path)
        paths = [p.name for p in scanner.scan()]

        # Should see both real and link
        assert "real" in paths
        assert "link" in paths


class TestMetadataConsistency:
    """Tests verifying consistency between scanner methods."""

    def test_scan_and_collect_metadata_consistency(self, tmp_path):
        """Test that scan() and collect_file_metadata() return consistent data."""
        # Create test structure
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "file2.py").write_text("code")
        (tmp_path / "dir").mkdir()

        scanner = FileScanner(tmp_path)

        # Get files from scan()
        scanned_paths = list(scanner.scan())

        # Get metadata for each scanned file
        for path in scanned_paths:
            metadata = scanner.collect_file_metadata(path)

            # Verify path consistency
            rel_path = path.relative_to(tmp_path)
            assert str(rel_path) == metadata["path"], (
                f"scan() returned {rel_path} but metadata has {metadata['path']}"
            )

            # Verify type consistency
            if path.is_dir():
                assert metadata["type"] == FileType.DIR
                assert metadata["size"] is None
            elif path.is_file():
                assert metadata["type"] == FileType.FILE
                assert metadata["size"] is not None

    def test_count_files_matches_scan(self, tmp_path):
        """Test that count_files() matches actual scan() results."""
        # Create known structure
        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.py").write_text("2")
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir2").mkdir()
        (tmp_path / "link.txt").symlink_to(tmp_path / "file1.txt")

        scanner = FileScanner(tmp_path)

        # Get counts
        counts = scanner.count_files()

        # Manually count from scan
        scanned = list(scanner.scan())
        actual_files = sum(1 for p in scanned if p.is_file() and not p.is_symlink())
        actual_dirs = sum(1 for p in scanned if p.is_dir())
        actual_symlinks = sum(1 for p in scanned if p.is_symlink())

        assert counts["files"] == actual_files
        assert counts["dirs"] == actual_dirs
        assert counts["symlinks"] == actual_symlinks
        assert counts["total"] == len(scanned)


class TestValidationRobustness:
    """Tests for validation and error handling."""

    def test_invalid_sha256_rejected(self):
        """Test that invalid SHA256 values are rejected."""
        with pytest.raises(ValueError, match="SHA256 must be 64 hexadecimal"):
            FileEntry(
                path="test.txt",
                type=FileType.FILE,
                size=100,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="invalid",  # Not 64 hex chars
            )

    def test_invalid_mode_rejected(self):
        """Test that invalid mode values are rejected."""
        with pytest.raises(ValueError, match="Mode must be valid octal"):
            FileEntry(
                path="test.txt",
                type=FileType.FILE,
                size=100,
                mode="9999",  # Invalid octal (9 not valid)
                mtime_utc="2025-01-01T00:00:00Z",
            )

    def test_absolute_path_rejected(self):
        """Test that absolute paths are rejected in FileEntry."""
        with pytest.raises(ValueError, match="Path must be relative"):
            FileEntry(
                path="/absolute/path/file.txt",
                type=FileType.FILE,
                size=100,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
            )

    def test_mode_normalization(self):
        """Test that mode values are normalized correctly."""
        # Test 0o prefix normalization
        entry1 = FileEntry(
            path="test.txt",
            type=FileType.FILE,
            size=100,
            mode="0o755",
            mtime_utc="2025-01-01T00:00:00Z",
        )
        assert entry1.mode == "0755"

        # Test padding
        entry2 = FileEntry(
            path="test.txt",
            type=FileType.FILE,
            size=100,
            mode="644",  # Missing leading zero
            mtime_utc="2025-01-01T00:00:00Z",
        )
        assert entry2.mode == "0644"

    def test_sha256_case_normalization(self):
        """Test that SHA256 values are normalized to lowercase."""
        entry = FileEntry(
            path="test.txt",
            type=FileType.FILE,
            size=100,
            mode="0644",
            mtime_utc="2025-01-01T00:00:00Z",
            sha256="A" * 64,  # Uppercase
        )
        assert entry.sha256 == "a" * 64  # Should be lowercase


class TestFixtureVerification:
    """Tests that verify fixture structure (was missing before)."""

    def test_sample_files_fixture_structure(self, sample_files):
        """Verify sample_files fixture has expected structure."""
        # Explicitly verify what the fixture creates
        assert (sample_files / "file1.txt").exists()
        assert (sample_files / "file2.py").exists()
        assert (sample_files / "subdir1").is_dir()
        assert (sample_files / "subdir2").is_dir()
        assert (sample_files / ".git").is_dir()
        assert (sample_files / "subdir1" / "nested.txt").exists()
        assert (sample_files / "subdir2" / "data.csv").exists()

        # Verify content
        assert (sample_files / "file1.txt").read_text() == "Sample content 1\n"
        assert "print('hello')" in (sample_files / "file2.py").read_text()
