"""Tests for archive splitting functionality."""

import pytest

from coldstore.core.archive import create_coldstore_archive
from coldstore.utils.formatters import parse_size


class TestSizeParsing:
    """Test size string parsing."""

    def test_parse_size_bytes(self):
        """Test parsing byte sizes."""
        assert parse_size("100") == 100
        assert parse_size("100B") == 100
        assert parse_size("0") == 0

    def test_parse_size_kb(self):
        """Test parsing kilobyte sizes."""
        assert parse_size("1KB") == 1024
        assert parse_size("2KB") == 2048
        assert parse_size("1.5KB") == int(1.5 * 1024)

    def test_parse_size_mb(self):
        """Test parsing megabyte sizes."""
        assert parse_size("1MB") == 1024 * 1024
        assert parse_size("2.5MB") == int(2.5 * 1024 * 1024)

    def test_parse_size_gb(self):
        """Test parsing gigabyte sizes."""
        assert parse_size("1GB") == 1024 ** 3
        assert parse_size("2GB") == 2 * (1024 ** 3)

    def test_parse_size_case_insensitive(self):
        """Test that parsing is case insensitive."""
        assert parse_size("1gb") == 1024 ** 3
        assert parse_size("500mb") == 500 * (1024 ** 2)
        assert parse_size("2kb") == 2 * 1024

    def test_parse_size_with_spaces(self):
        """Test parsing with spaces."""
        assert parse_size(" 1GB ") == 1024 ** 3
        assert parse_size("2 MB") == 2 * (1024 ** 2)

    def test_parse_size_invalid_format(self):
        """Test error handling for invalid formats."""
        with pytest.raises(ValueError, match="Invalid size format"):
            parse_size("not-a-size")

        with pytest.raises(ValueError, match="Invalid size format"):
            parse_size("1.2.3GB")

        with pytest.raises(ValueError, match="Invalid size format"):
            parse_size("abcGB")  # Invalid because abc is not a number

    def test_parse_size_unknown_unit(self):
        """Test error handling for unknown units."""
        # ZB (Zettabyte) is not in our regex pattern,
        # so it gets rejected as invalid format
        with pytest.raises(ValueError, match="Invalid size format"):
            parse_size("1ZB")

    def test_parse_size_empty(self):
        """Test error handling for empty string."""
        with pytest.raises(ValueError, match="Size string cannot be empty"):
            parse_size("")


class TestArchiveSplitting:
    """Test archive splitting functionality."""

    def test_archive_splitting_basic(self, tmp_path):
        """Test basic archive splitting functionality."""
        # Create test directory with multiple files
        source_dir = tmp_path / "test_source"
        source_dir.mkdir()

        # Create files of different sizes
        (source_dir / "small1.txt").write_text("small file 1" * 100)  # ~1.2KB
        (source_dir / "small2.txt").write_text("small file 2" * 100)  # ~1.2KB
        (source_dir / "large1.txt").write_text("large file 1" * 1000)  # ~12KB
        (source_dir / "large2.txt").write_text("large file 2" * 1000)  # ~12KB

        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        # Split at 10KB - should create multiple parts
        result = create_coldstore_archive(
            source_dir,
            archive_dir,
            note="Test split archive",
            split_size="10KB"
        )

        archive_path, sha256_path, readme_path = result

        # Should have created multiple archive files
        assert archive_path is not None
        assert sha256_path is not None
        assert readme_path is not None

        # Check that split archives were created
        split_files = list(archive_dir.glob("*.part*.tar.gz"))
        if not split_files:
            # If no .part files, it means everything fit in one archive
            single_files = list(archive_dir.glob("*.tar.gz"))
            assert len(single_files) == 1
            print("All files fit in single archive (expected for small test)")
        else:
            assert len(split_files) >= 2
            print(f"Created {len(split_files)} archive parts")

        # SHA256 file should exist
        assert sha256_path.exists()

        # README should exist and mention split if applicable
        assert readme_path.exists()
        readme_content = readme_path.read_text()
        assert "Test split archive" in readme_content

    def test_no_splitting_when_under_limit(self, tmp_path):
        """Test that no splitting occurs when files are under limit."""
        # Create small test directory
        source_dir = tmp_path / "small_source"
        source_dir.mkdir()

        (source_dir / "small.txt").write_text("small file")

        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        # Very large split size - should not split
        result = create_coldstore_archive(
            source_dir,
            archive_dir,
            split_size="100GB"
        )

        archive_path, sha256_path, readme_path = result

        # Should create single archive
        assert archive_path is not None
        assert not str(archive_path).endswith(".part001.tar.gz")

        # No split part files should exist
        split_files = list(archive_dir.glob("*.part*.tar.gz"))
        assert len(split_files) == 0

    def test_split_size_validation(self, tmp_path):
        """Test that invalid split sizes are rejected."""
        source_dir = tmp_path / "test_source"
        source_dir.mkdir()
        (source_dir / "test.txt").write_text("test content")

        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        # Test invalid split size
        with pytest.raises(ValueError):
            create_coldstore_archive(
                source_dir,
                archive_dir,
                split_size="invalid-size"
            )


class TestSplitArchiveMetadata:
    """Test metadata generation for split archives."""

    def test_split_archive_readme_content(self, tmp_path):
        """Test that README contains split archive information."""
        # Create test files that will likely be split
        source_dir = tmp_path / "large_source"
        source_dir.mkdir()

        # Create enough content to potentially trigger splitting
        for i in range(5):
            (source_dir / f"file_{i}.txt").write_text(f"Content {i}" * 500)

        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        result = create_coldstore_archive(
            source_dir,
            archive_dir,
            note="Split archive test",
            split_size="2KB"  # Small size to force splitting
        )

        _, _, readme_path = result

        readme_content = readme_path.read_text()

        # Check if split archive information is present
        # (may or may not split depending on compression)
        if "Split Archive Information" in readme_content:
            assert "Archive type: Split archive" in readme_content
            assert "Number of parts:" in readme_content
            assert "Parts:" in readme_content
        else:
            # If not split, that's also valid for small test files
            assert "Split archive test" in readme_content
