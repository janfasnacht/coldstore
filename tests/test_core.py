"""Tests for core archiving functionality."""

import hashlib
import tarfile

import pytest

from archive_project.core.archiver import archive_project
from archive_project.core.metadata import get_metadata


class TestMetadata:
    """Test metadata collection functionality."""

    def test_metadata_basic(self, tmp_path):
        """Test basic metadata collection."""
        # Create test structure
        test_dir = tmp_path / "test_metadata"
        test_dir.mkdir()

        (test_dir / "file1.txt").write_text("Hello world")
        (test_dir / "file2.py").write_text("print('test')")
        sub_dir = test_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "file3.json").write_text('{"key": "value"}')

        # Get metadata
        meta = get_metadata(test_dir)

        # Verify metadata
        assert meta["file_count"] == 3
        assert meta["directory_count"] == 1
        assert meta["total_size_bytes"] > 0
        assert meta["total_size_human"] != "0B"
        assert "earliest_date" in meta
        assert "latest_date" in meta
        assert len(meta["top_file_types"]) > 0

    def test_metadata_empty_directory(self, tmp_path):
        """Test metadata for empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        meta = get_metadata(empty_dir)

        assert meta["file_count"] == 0
        assert meta["directory_count"] == 0
        assert meta["total_size_bytes"] == 0

    def test_metadata_file_types(self, tmp_path):
        """Test file type tracking."""
        test_dir = tmp_path / "test_types"
        test_dir.mkdir()

        # Create files with different extensions
        (test_dir / "doc1.txt").write_text("text")
        (test_dir / "doc2.txt").write_text("more text")
        (test_dir / "script.py").write_text("code")
        (test_dir / "data.json").write_text("{}")

        meta = get_metadata(test_dir)

        # Check file types are tracked
        file_types = dict(meta["top_file_types"])
        assert file_types.get(".txt", 0) == 2
        assert file_types.get(".py", 0) == 1
        assert file_types.get(".json", 0) == 1


class TestArchiver:
    """Test main archiving functionality."""

    def test_archive_basic(self, tmp_path):
        """Test basic archive creation."""
        # Create source directory
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("test content")

        # Create archive directory
        archive_dir = tmp_path / "archives"

        # Archive
        archive_path, sha256_path, readme_path = archive_project(
            source_path=source_dir, archive_dir=archive_dir, note="Test archive"
        )

        # Verify files created
        assert archive_path.exists()
        assert sha256_path.exists()
        assert readme_path.exists()

        # Verify archive contents
        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getnames()
            assert "source/file.txt" in members

        # Verify checksum
        with open(archive_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()

        checksum_content = sha256_path.read_text()
        stored_hash = checksum_content.split()[0]
        assert actual_hash == stored_hash

    def test_archive_custom_name(self, tmp_path):
        """Test custom archive naming."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("test")

        archive_dir = tmp_path / "archives"

        archive_path, _, _ = archive_project(
            source_path=source_dir, archive_dir=archive_dir, archive_name="custom-name"
        )

        assert archive_path.name == "custom-name.tar.gz"

    def test_archive_no_archive_flag(self, tmp_path):
        """Test --no-archive flag (metadata only)."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("test")

        archive_dir = tmp_path / "archives"

        archive_path, sha256_path, readme_path = archive_project(
            source_path=source_dir, archive_dir=archive_dir, do_archive=False
        )

        # Only README should be created
        assert archive_path is None
        assert sha256_path is None
        assert readme_path.exists()

    def test_archive_exclusions(self, tmp_path):
        """Test file exclusion patterns."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "keep.txt").write_text("keep this")
        (source_dir / "exclude.log").write_text("exclude this")
        (source_dir / "keep.py").write_text("keep this too")

        archive_dir = tmp_path / "archives"

        archive_path, _, _ = archive_project(
            source_path=source_dir, archive_dir=archive_dir, exclude_patterns=["*.log"]
        )

        # Verify exclusions
        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getnames()
            assert "source/keep.txt" in members
            assert "source/keep.py" in members
            assert "source/exclude.log" not in members

    def test_archive_compression_levels(self, tmp_path):
        """Test different compression levels."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        # Create a larger file for noticeable compression differences
        (source_dir / "large.txt").write_text("x" * 10000)

        archive_dir = tmp_path / "archives"

        # Test lowest compression (fastest)
        archive_1, _, _ = archive_project(
            source_path=source_dir,
            archive_dir=archive_dir,
            archive_name="level-1",
            compress_level=1,
        )

        # Test highest compression (smallest)
        archive_9, _, _ = archive_project(
            source_path=source_dir,
            archive_dir=archive_dir,
            archive_name="level-9",
            compress_level=9,
        )

        # Higher compression should result in smaller file
        size_1 = archive_1.stat().st_size
        size_9 = archive_9.stat().st_size
        assert size_9 <= size_1

    def test_archive_nonexistent_source(self, tmp_path):
        """Test error handling for nonexistent source."""
        nonexistent = tmp_path / "nonexistent"
        archive_dir = tmp_path / "archives"

        with pytest.raises(FileNotFoundError):
            archive_project(source_path=nonexistent, archive_dir=archive_dir)

    def test_archive_readme_content(self, tmp_path):
        """Test README content generation."""
        source_dir = tmp_path / "test_project"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("content")

        archive_dir = tmp_path / "archives"

        _, _, readme_path = archive_project(
            source_path=source_dir,
            archive_dir=archive_dir,
            note="Custom note for testing",
        )

        readme_content = readme_path.read_text()

        # Verify key sections
        assert "# Archive:" in readme_content
        assert "## Source Information" in readme_content
        assert "## Contents Summary" in readme_content
        assert "## Notes" in readme_content
        assert "Custom note for testing" in readme_content
        assert "## Directory Structure" in readme_content
        assert "test_project" in readme_content
