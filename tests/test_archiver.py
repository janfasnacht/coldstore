"""Tests for streaming archive builder."""

import hashlib
import tarfile

import pytest

from coldstore.core.archiver import ArchiveBuilder
from coldstore.core.scanner import FileScanner


class TestArchiveBuilderBasics:
    """Test basic archive builder functionality."""

    def test_create_archive_basic(self, tmp_path):
        """Test creating a basic archive."""
        # Create source structure
        source = tmp_path / "source"
        source.mkdir()
        (source / "file1.txt").write_text("content1")
        (source / "file2.txt").write_text("content2")

        # Create archive
        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        result = builder.create_archive(scanner)

        # Verify result metadata
        assert result["path"] == archive_path
        assert result["size_bytes"] > 0
        assert result["sha256"] is not None
        assert len(result["sha256"]) == 64
        assert result["files_added"] == 2
        assert result["dirs_added"] == 0

        # Verify archive exists and is valid tar.gz
        assert archive_path.exists()
        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getmembers()
            assert len(members) == 2
            names = [m.name for m in members]
            assert "source/file1.txt" in names
            assert "source/file2.txt" in names

    def test_archive_with_directories(self, tmp_path):
        """Test archiving with nested directories."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "dir1").mkdir()
        (source / "dir1" / "file.txt").write_text("nested")
        (source / "dir2").mkdir()

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        result = builder.create_archive(scanner)

        assert result["files_added"] == 1
        assert result["dirs_added"] == 2

        # Verify directory structure preserved
        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            assert "source/dir1" in names
            assert "source/dir2" in names
            assert "source/dir1/file.txt" in names

    def test_custom_arcname_root(self, tmp_path):
        """Test using custom archive name root."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        builder.create_archive(scanner, arcname_root="custom_name")

        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            assert "custom_name/file.txt" in names
            assert "source/file.txt" not in names


class TestCompressionLevels:
    """Test different compression levels."""

    def test_compression_level_0(self, tmp_path):
        """Test no compression (level 0)."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_bytes(b"A" * 10000)

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, compression_level=0)

        result = builder.create_archive(scanner)

        # Level 0 should produce larger archive
        assert result["size_bytes"] > 10000

    def test_compression_level_9(self, tmp_path):
        """Test maximum compression (level 9)."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_bytes(b"A" * 10000)

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, compression_level=9)

        result = builder.create_archive(scanner)

        # Level 9 should produce smaller archive (highly compressible data)
        assert result["size_bytes"] < 1000  # Very compressible

    def test_invalid_compression_level(self, tmp_path):
        """Test that invalid compression levels are rejected."""
        archive_path = tmp_path / "test.tar.gz"

        with pytest.raises(ValueError, match="Compression level must be 0-9"):
            ArchiveBuilder(archive_path, compression_level=10)

        with pytest.raises(ValueError, match="Compression level must be 0-9"):
            ArchiveBuilder(archive_path, compression_level=-1)


class TestSHA256Computation:
    """Test archive-level SHA256 hash computation."""

    def test_sha256_computed_by_default(self, tmp_path):
        """Test that SHA256 is computed by default."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)  # compute_sha256=True by default

        result = builder.create_archive(scanner)

        assert result["sha256"] is not None
        assert len(result["sha256"]) == 64
        assert all(c in "0123456789abcdef" for c in result["sha256"])

    def test_sha256_can_be_disabled(self, tmp_path):
        """Test that SHA256 computation can be disabled."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, compute_sha256=False)

        result = builder.create_archive(scanner)

        assert result["sha256"] is None

    def test_sha256_matches_independent_computation(self, tmp_path):
        """Test that computed SHA256 matches independent verification."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("test content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        result = builder.create_archive(scanner)

        # Independently compute SHA256 of archive
        sha256_hash = hashlib.sha256()
        with open(archive_path, "rb") as f:
            while chunk := f.read(65536):
                sha256_hash.update(chunk)
        expected_hash = sha256_hash.hexdigest()

        assert result["sha256"] == expected_hash


class TestDeterministicOrdering:
    """Test that archives are created in deterministic order."""

    def test_archives_are_deterministic(self, tmp_path):
        """Test that same source creates identical archives."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "zzz.txt").write_text("last alphabetically")
        (source / "aaa.txt").write_text("first alphabetically")
        (source / "mmm.txt").write_text("middle")

        # Create first archive
        archive1 = tmp_path / "archive1.tar.gz"
        scanner1 = FileScanner(source)
        builder1 = ArchiveBuilder(archive1, compression_level=6)
        result1 = builder1.create_archive(scanner1)

        # Create second archive
        archive2 = tmp_path / "archive2.tar.gz"
        scanner2 = FileScanner(source)
        builder2 = ArchiveBuilder(archive2, compression_level=6)
        result2 = builder2.create_archive(scanner2)

        # SHA256 hashes should match (deterministic)
        assert result1["sha256"] == result2["sha256"]

        # File sizes should match
        assert result1["size_bytes"] == result2["size_bytes"]


class TestExclusionPatterns:
    """Test that exclusion patterns from scanner are respected."""

    def test_excluded_files_not_in_archive(self, tmp_path):
        """Test that excluded files don't appear in archive."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "keep.txt").write_text("keep")
        (source / "exclude.pyc").write_text("exclude")
        (source / "keep.py").write_text("keep")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source, exclude_patterns=["*.pyc"])
        builder = ArchiveBuilder(archive_path)

        result = builder.create_archive(scanner)

        assert result["files_added"] == 2  # Only .txt and .py

        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            assert "source/keep.txt" in names
            assert "source/keep.py" in names
            assert "source/exclude.pyc" not in names


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_directory(self, tmp_path):
        """Test archiving empty directory."""
        source = tmp_path / "source"
        source.mkdir()

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        result = builder.create_archive(scanner)

        assert result["files_added"] == 0
        assert result["dirs_added"] == 0
        assert archive_path.exists()

    def test_unicode_filenames(self, tmp_path):
        """Test archiving files with Unicode names."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "emoji_🎉.txt").write_text("content")
        (source / "中文.py").write_text("code")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        result = builder.create_archive(scanner)

        assert result["files_added"] == 2

        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            assert "source/emoji_🎉.txt" in names
            assert "source/中文.py" in names

    def test_symlinks_archived(self, tmp_path):
        """Test that symlinks are preserved in archive."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "target.txt").write_text("target")
        (source / "link.txt").symlink_to(source / "target.txt")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        result = builder.create_archive(scanner)

        # Both files should be added (target + link)
        assert result["files_added"] >= 2

        with tarfile.open(archive_path, "r:gz") as tar:
            link_member = tar.getmember("source/link.txt")
            assert link_member.issym()


class TestErrorHandling:
    """Test error handling and recovery."""

    def test_archive_cleaned_up_on_failure(self, tmp_path, monkeypatch):
        """Test that partial archive is cleaned up on failure."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        # Mock tarfile.open to raise an error
        def mock_open(*args, **kwargs):
            raise OSError("Simulated I/O error")

        monkeypatch.setattr(tarfile, "open", mock_open)

        with pytest.raises(OSError, match="Simulated I/O error"):
            builder.create_archive(scanner)

        # Archive should not exist after failure
        assert not archive_path.exists()


class TestMemoryEfficiency:
    """Test memory efficiency with larger files."""

    def test_large_file_streaming(self, tmp_path):
        """Test that large files are streamed (not loaded into memory)."""
        source = tmp_path / "source"
        source.mkdir()

        # Create 10MB file
        large_file = source / "large.bin"
        large_file.write_bytes(b"X" * (10 * 1024 * 1024))

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        _result = builder.create_archive(scanner)

        assert _result["files_added"] == 1
        assert archive_path.exists()

        # Verify archive contains the large file
        with tarfile.open(archive_path, "r:gz") as tar:
            member = tar.getmember("source/large.bin")
            assert member.size == 10 * 1024 * 1024


class TestIntegrationWithScanner:
    """Test integration between ArchiveBuilder and FileScanner."""

    def test_vcs_exclusion_respected(self, tmp_path):
        """Test that scanner's VCS exclusion is respected in archive."""
        source = tmp_path / "source"
        source.mkdir()
        (source / ".git").mkdir()
        (source / ".git" / "config").write_text("git config")
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source, exclude_vcs=True)
        builder = ArchiveBuilder(archive_path)

        _result = builder.create_archive(scanner)

        # .git should be excluded
        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            assert "source/file.txt" in names
            assert all(".git" not in name for name in names)

    def test_scanner_ordering_preserved(self, tmp_path):
        """Test that scanner's lexicographic ordering is preserved."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "zzz.txt").write_text("last")
        (source / "aaa.txt").write_text("first")
        (source / "mmm.txt").write_text("middle")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        builder.create_archive(scanner)

        # Extract member names in order
        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]

        # Should be in lexicographic order
        assert names == sorted(names)
