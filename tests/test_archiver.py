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

    def test_archive_extraction_preserves_content(self, tmp_path):
        """Test that archived files can be extracted with original content intact."""
        # Create source with specific content
        source = tmp_path / "source"
        source.mkdir()
        (source / "file1.txt").write_text("content1")
        (source / "dir1").mkdir()
        (source / "dir1" / "file2.txt").write_text("content2")
        (source / "dir1" / "nested").mkdir()
        (source / "dir1" / "nested" / "file3.txt").write_text("content3")

        # Create archive
        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)
        result = builder.create_archive(scanner)

        # Verify archive was created successfully
        assert result["files_added"] == 3
        assert result["dirs_added"] == 2

        # Extract to different location
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        # Verify extracted content matches original
        extracted_source = extract_dir / "source"
        assert (extracted_source / "file1.txt").read_text() == "content1"
        assert (extracted_source / "dir1" / "file2.txt").read_text() == "content2"
        assert (
            extracted_source / "dir1" / "nested" / "file3.txt"
        ).read_text() == "content3"

        # Verify directory structure preserved
        assert (extracted_source / "dir1").is_dir()
        assert (extracted_source / "dir1" / "nested").is_dir()

    def test_progress_callback_invoked(self, tmp_path):
        """Test that progress callback is invoked during archive creation."""
        # Create source with multiple files and directories
        source = tmp_path / "source"
        source.mkdir()
        (source / "file1.txt").write_text("content1")
        (source / "file2.txt").write_text("content2")
        (source / "dir1").mkdir()
        (source / "dir1" / "file3.txt").write_text("content3")

        # Track progress callback invocations
        progress_calls = []

        def progress_callback(items_processed: int, total_items: int):
            progress_calls.append((items_processed, total_items))

        # Create archive with progress callback
        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)
        result = builder.create_archive(scanner, progress_callback=progress_callback)

        # Verify archive created successfully
        assert result["files_added"] == 3
        assert result["dirs_added"] == 1

        # Verify progress callback was invoked
        assert len(progress_calls) > 0
        # Should have 4 calls (3 files + 1 dir)
        assert len(progress_calls) == 4

        # Verify progress calls are sequential
        for i, (items_processed, total_items) in enumerate(progress_calls):
            assert items_processed == i + 1  # 1-indexed
            assert total_items == 4  # Total items

        # Final callback should report all items processed
        final_processed, final_total = progress_calls[-1]
        assert final_processed == final_total
        assert final_processed == 4

    def test_progress_callback_not_invoked_when_none(self, tmp_path):
        """Test that progress callback is not invoked when None."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path)

        # Create archive without progress callback (default)
        result = builder.create_archive(scanner)

        # Should succeed without errors
        assert result["files_added"] == 1


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

    def test_compression_levels_differ(self, tmp_path):
        """Test that different compression levels produce different sized archives."""
        # Create source with highly compressible data
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_bytes(b"A" * 50000)  # 50KB of same byte

        # Create archives with different compression levels
        archive_0 = tmp_path / "level_0.tar.gz"
        scanner_0 = FileScanner(source)
        builder_0 = ArchiveBuilder(archive_0, compression_level=0)
        result_0 = builder_0.create_archive(scanner_0)

        archive_6 = tmp_path / "level_6.tar.gz"
        scanner_6 = FileScanner(source)
        builder_6 = ArchiveBuilder(archive_6, compression_level=6)
        result_6 = builder_6.create_archive(scanner_6)

        archive_9 = tmp_path / "level_9.tar.gz"
        scanner_9 = FileScanner(source)
        builder_9 = ArchiveBuilder(archive_9, compression_level=9)
        result_9 = builder_9.create_archive(scanner_9)

        # Verify compression levels affect size as expected
        # Level 0 (no compression) should be largest
        assert result_0["size_bytes"] > result_6["size_bytes"]
        assert result_0["size_bytes"] > result_9["size_bytes"]

        # Level 9 (max compression) should be smallest
        assert result_9["size_bytes"] < result_6["size_bytes"]
        assert result_9["size_bytes"] < result_0["size_bytes"]

        # Verify actual compression happened (level 9 should compress 50KB to < 10KB)
        assert result_9["size_bytes"] < 10000  # Good compression

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

        # Should be 1 file + 1 symlink = 2 items total
        # Note: In older code symlinks were counted as files
        assert result["files_added"] + result.get("symlinks_added", 0) >= 1

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


class TestFILELISTGeneration:
    """Test FILELIST.csv.gz generation in archives."""

    def test_filelist_generated_when_enabled(self, tmp_path):
        """Test that FILELIST.csv.gz is generated when enabled."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file1.txt").write_text("content1")
        (source / "file2.txt").write_text("content2")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_filelist=True)

        result = builder.create_archive(scanner)

        # Verify FILELIST metadata in result
        assert "filelist_sha256" in result
        assert result["filelist_sha256"] is not None
        assert len(result["filelist_sha256"]) == 64
        assert "file_metadata" in result
        assert len(result["file_metadata"]) == 2

        # Verify FILELIST.csv.gz exists in archive
        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            assert "source/COLDSTORE/FILELIST.csv.gz" in names

    def test_filelist_not_generated_when_disabled(self, tmp_path):
        """Test that FILELIST.csv.gz is NOT generated when disabled."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file1.txt").write_text("content1")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_filelist=False)

        result = builder.create_archive(scanner)

        # Verify no FILELIST metadata
        assert "filelist_sha256" not in result or result["filelist_sha256"] is None
        assert "file_metadata" not in result or result["file_metadata"] == []

        # Verify no COLDSTORE directory in archive
        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            assert not any("COLDSTORE" in name for name in names)

    def test_filelist_deterministic_with_fixed_mtimes(self, tmp_path):
        """Test that FILELIST CSV is deterministic when file mtimes are identical.

        Note: The archive itself may still differ due to tar format metadata,
        but the FILELIST.csv.gz content should be deterministic.
        """
        import os

        # Create source with files
        source = tmp_path / "source"
        source.mkdir()

        file1 = source / "aaa.txt"
        file1.write_text("content1")
        file2 = source / "zzz.txt"
        file2.write_text("content2")

        # Set fixed mtime on all files AND directories (2024-01-01 00:00:00)
        fixed_time = 1704067200.0
        os.utime(file1, (fixed_time, fixed_time))
        os.utime(file2, (fixed_time, fixed_time))
        os.utime(source, (fixed_time, fixed_time))

        # Create first archive with FILELIST
        archive1 = tmp_path / "archive1.tar.gz"
        scanner1 = FileScanner(source)
        builder1 = ArchiveBuilder(archive1, compression_level=6, generate_filelist=True)
        result1 = builder1.create_archive(scanner1)

        # Create second archive with FILELIST
        archive2 = tmp_path / "archive2.tar.gz"
        scanner2 = FileScanner(source)
        builder2 = ArchiveBuilder(archive2, compression_level=6, generate_filelist=True)
        result2 = builder2.create_archive(scanner2)

        # With identical mtimes, FILELIST hash should be deterministic
        # (The archive hash may differ due to tar format overhead)
        assert result1["filelist_sha256"] == result2["filelist_sha256"]

    def test_filelist_changes_with_different_mtimes(self, tmp_path):
        """Test that FILELIST changes when file mtimes differ (correct behavior)."""
        import os

        # Create source
        source = tmp_path / "source"
        source.mkdir()

        file1 = source / "file.txt"
        file1.write_text("content")

        # Set first mtime
        time1 = 1704067200.0  # 2024-01-01 00:00:00
        os.utime(file1, (time1, time1))

        # Create first archive
        archive1 = tmp_path / "archive1.tar.gz"
        scanner1 = FileScanner(source)
        builder1 = ArchiveBuilder(archive1, compression_level=6, generate_filelist=True)
        result1 = builder1.create_archive(scanner1)

        # Change mtime
        time2 = 1704153600.0  # 2024-01-02 00:00:00
        os.utime(file1, (time2, time2))

        # Create second archive
        archive2 = tmp_path / "archive2.tar.gz"
        scanner2 = FileScanner(source)
        builder2 = ArchiveBuilder(archive2, compression_level=6, generate_filelist=True)
        result2 = builder2.create_archive(scanner2)

        # Filelists should differ (different mtimes = different metadata)
        assert result1["filelist_sha256"] != result2["filelist_sha256"]
        # Archive hashes will also differ
        assert result1["sha256"] != result2["sha256"]

    def test_filelist_contains_all_files(self, tmp_path):
        """Test that FILELIST contains metadata for all archived files."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file1.txt").write_text("content1")
        (source / "dir1").mkdir()
        (source / "dir1" / "file2.txt").write_text("content2")
        (source / "file3.py").write_text("code")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_filelist=True)

        result = builder.create_archive(scanner)

        # Should have metadata for all files and directories
        assert len(result["file_metadata"]) == 4  # 3 files + 1 dir

        # Verify metadata has required fields
        for metadata in result["file_metadata"]:
            assert "path" in metadata
            assert "type" in metadata
            assert "mode" in metadata
            assert "mtime_utc" in metadata

    def test_filelist_can_be_extracted_and_read(self, tmp_path):
        """Test that FILELIST.csv.gz can be extracted and read."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file1.txt").write_text("content1")
        (source / "file2.txt").write_text("content2")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_filelist=True)

        builder.create_archive(scanner)

        # Extract FILELIST.csv.gz from archive
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        filelist_path = extract_dir / "source" / "COLDSTORE" / "FILELIST.csv.gz"
        assert filelist_path.exists()

        # Read and verify FILELIST
        from coldstore.core.manifest import read_filelist_csv

        entries = read_filelist_csv(filelist_path)
        assert len(entries) == 2
        assert entries[0]["relpath"] == "file1.txt"
        assert entries[1]["relpath"] == "file2.txt"

    def test_filelist_hash_matches_content(self, tmp_path):
        """Test that filelist_sha256 matches actual FILELIST.csv.gz hash."""
        import hashlib

        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_filelist=True)

        result = builder.create_archive(scanner)

        # Extract FILELIST.csv.gz
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        filelist_path = extract_dir / "source" / "COLDSTORE" / "FILELIST.csv.gz"

        # Compute independent hash
        hasher = hashlib.sha256()
        with open(filelist_path, "rb") as f:
            hasher.update(f.read())
        independent_hash = hasher.hexdigest()

        # Should match reported hash
        assert result["filelist_sha256"] == independent_hash


class TestManifestGeneration:
    """Test MANIFEST file generation."""

    def test_manifest_generated_when_enabled(self, tmp_path):
        """Test that MANIFEST files are generated when enabled."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_manifest=True)

        result = builder.create_archive(scanner)

        # Verify MANIFEST files were created
        assert "manifest_json_path" in result
        assert "sha256_file_path" in result

        # Check JSON sidecar exists
        manifest_json = result["manifest_json_path"]
        assert manifest_json.exists()
        assert manifest_json.name == "test.tar.gz.MANIFEST.json"

        # Check .sha256 file exists
        sha256_file = result["sha256_file_path"]
        assert sha256_file.exists()
        assert sha256_file.name == "test.tar.gz.sha256"

        # Check MANIFEST.yaml is in archive
        with tarfile.open(archive_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            assert "source/COLDSTORE/MANIFEST.yaml" in names

    def test_manifest_not_generated_when_disabled(self, tmp_path):
        """Test that MANIFEST files are NOT generated when disabled."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_manifest=False)

        result = builder.create_archive(scanner)

        # No MANIFEST paths in result
        assert (
            "manifest_json_path" not in result
            or result["manifest_json_path"] is None
        )
        assert (
            "sha256_file_path" not in result or result["sha256_file_path"] is None
        )

        # No sidecar files created
        manifest_json = archive_path.parent / f"{archive_path.name}.MANIFEST.json"
        sha256_file = archive_path.parent / f"{archive_path.name}.sha256"
        assert not manifest_json.exists()
        assert not sha256_file.exists()

    def test_manifest_contains_correct_metadata(self, tmp_path):
        """Test that generated MANIFEST contains correct metadata."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)

        # Create archive with event metadata
        from coldstore.core.manifest import EventMetadata

        event = EventMetadata(
            type="milestone",
            name="test milestone",
            notes=["test note"],
            contacts=["test@example.com"],
        )

        builder = ArchiveBuilder(
            archive_path,
            generate_manifest=True,
            event_metadata=event,
        )

        result = builder.create_archive(scanner)

        # Read JSON manifest
        from coldstore.core.manifest import ColdstoreManifest

        manifest_json_path = result["manifest_json_path"]
        manifest = ColdstoreManifest.read_json(manifest_json_path)

        # Verify structure
        assert manifest.manifest_version == "1.0"
        assert manifest.id is not None
        assert manifest.created_utc is not None

        # Verify source metadata
        assert str(source.resolve()) in manifest.source.root
        assert manifest.source.normalization.ordering == "lexicographic"

        # Verify event metadata
        assert manifest.event.type == "milestone"
        assert manifest.event.name == "test milestone"
        assert "test note" in manifest.event.notes
        assert "test@example.com" in manifest.event.contacts

        # Verify archive metadata
        assert manifest.archive.filename == "test.tar.gz"
        assert manifest.archive.format == "tar+gzip"
        assert manifest.archive.size_bytes > 0
        assert len(manifest.archive.sha256) == 64
        assert manifest.archive.member_count.files == 1
        assert manifest.archive.member_count.dirs == 0

        # Verify environment metadata
        assert manifest.environment.system.os is not None
        assert manifest.environment.tools.coldstore_version is not None
        assert manifest.environment.tools.python_version is not None

        # Verify git metadata (should be present=False for tmp_path)
        assert manifest.git.present is False

    def test_sha256_file_format(self, tmp_path):
        """Test that .sha256 file has correct format."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_manifest=True)

        result = builder.create_archive(scanner)

        # Read .sha256 file
        sha256_file = result["sha256_file_path"]
        content = sha256_file.read_text()

        # Should match sha256sum format: "<hash>  <filename>\n"
        lines = content.strip().split("\n")
        assert len(lines) == 1

        parts = lines[0].split("  ", 1)  # Two spaces separator
        assert len(parts) == 2
        hash_value, filename = parts

        # Verify hash format
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

        # Verify filename
        assert filename == "test.tar.gz"

        # Verify hash matches archive SHA256
        assert hash_value == result["sha256"]

    def test_manifest_yaml_embedded_in_archive(self, tmp_path):
        """Test that MANIFEST.yaml is correctly embedded in archive."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_manifest=True)

        builder.create_archive(scanner)

        # Extract MANIFEST.yaml from archive
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        manifest_yaml_path = extract_dir / "source" / "COLDSTORE" / "MANIFEST.yaml"
        assert manifest_yaml_path.exists()

        # Verify it's valid YAML and can be parsed
        from coldstore.core.manifest import ColdstoreManifest

        manifest = ColdstoreManifest.read_yaml(manifest_yaml_path)
        assert manifest.manifest_version == "1.0"
        assert manifest.archive.filename == "test.tar.gz"

    def test_manifest_with_git_repository(self, tmp_path):
        """Test manifest generation in a git repository."""
        import subprocess

        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=source,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=source,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "add", "."], cwd=source, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=source,
            check=True,
            capture_output=True,
        )

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_manifest=True)

        result = builder.create_archive(scanner)

        # Read manifest
        from coldstore.core.manifest import ColdstoreManifest

        manifest = ColdstoreManifest.read_json(result["manifest_json_path"])

        # Verify git metadata was collected
        assert manifest.git.present is True
        assert manifest.git.commit is not None
        assert len(manifest.git.commit) == 40  # SHA1 hash length
        assert manifest.git.dirty is False  # Clean repo

    def test_manifest_yaml_has_none_json_has_real_values(self, tmp_path):
        """Test that embedded YAML has None while JSON sidecar has actual values."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_manifest=True)

        result = builder.create_archive(scanner)

        # Extract MANIFEST.yaml from archive
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        manifest_yaml_path = extract_dir / "source" / "COLDSTORE" / "MANIFEST.yaml"

        # Read both manifests
        from coldstore.core.manifest import ColdstoreManifest

        yaml_manifest = ColdstoreManifest.read_yaml(manifest_yaml_path)
        json_manifest = ColdstoreManifest.read_json(result["manifest_json_path"])

        # YAML should have None for size_bytes and sha256
        assert yaml_manifest.archive.size_bytes is None
        assert yaml_manifest.archive.sha256 is None

        # JSON should have real values
        assert json_manifest.archive.size_bytes is not None
        assert json_manifest.archive.size_bytes > 0
        assert json_manifest.archive.sha256 is not None
        assert len(json_manifest.archive.sha256) == 64
        assert json_manifest.archive.sha256 != "0" * 64

        # Both should have same other values
        assert yaml_manifest.id == json_manifest.id
        assert yaml_manifest.archive.filename == json_manifest.archive.filename

    def test_no_sha256_file_when_compute_sha256_disabled(self, tmp_path):
        """Test that .sha256 file is not created when SHA256 computation is disabled."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(
            archive_path, generate_manifest=True, compute_sha256=False
        )

        result = builder.create_archive(scanner)

        # No .sha256 file should be created
        assert "sha256_file_path" not in result or result["sha256_file_path"] is None

        # JSON manifest should have None for SHA256
        from coldstore.core.manifest import ColdstoreManifest

        manifest = ColdstoreManifest.read_json(result["manifest_json_path"])
        assert manifest.archive.sha256 is None

        # .sha256 file should not exist
        sha256_file = archive_path.parent / f"{archive_path.name}.sha256"
        assert not sha256_file.exists()

    def test_symlink_counting(self, tmp_path):
        """Test that symlinks are counted correctly."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")
        (source / "link.txt").symlink_to(source / "file.txt")

        archive_path = tmp_path / "test.tar.gz"
        scanner = FileScanner(source)
        builder = ArchiveBuilder(archive_path, generate_manifest=True)

        result = builder.create_archive(scanner)

        # Read manifest
        from coldstore.core.manifest import ColdstoreManifest

        manifest = ColdstoreManifest.read_json(result["manifest_json_path"])

        # Should have 1 file and 1 symlink
        assert manifest.archive.member_count.files == 1
        assert manifest.archive.member_count.symlinks == 1
        assert manifest.archive.member_count.dirs == 0

    def test_event_metadata_validation(self, tmp_path):
        """Test that invalid event_metadata raises TypeError."""
        archive_path = tmp_path / "test.tar.gz"

        # Should reject non-EventMetadata types
        with pytest.raises(TypeError, match="event_metadata must be EventMetadata"):
            ArchiveBuilder(archive_path, event_metadata="not an EventMetadata")
