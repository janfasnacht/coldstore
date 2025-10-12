"""Tests for file system scanner."""

import pytest
from pathlib import Path

from coldstore.core.scanner import DEFAULT_VCS_DIRS, FileScanner, scan_directory
from coldstore.core.manifest import FileEntry, FileType


class TestFileScannerBasics:
    """Test basic file scanner functionality."""

    def test_scanner_finds_exact_files(self, tmp_path):
        """Test scanner finds exactly the expected files."""
        # Create known structure
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.md").write_text("content3")

        scanner = FileScanner(tmp_path)
        paths = sorted([str(p.relative_to(tmp_path)) for p in scanner.scan()])

        # Verify EXACT list of files (not just any())
        expected = sorted(["file1.txt", "file2.py", "subdir", "subdir/file3.md"])
        assert paths == expected, f"Expected {expected} but got {paths}"

    def test_exclusions_verify_both_inclusion_and_exclusion(self, tmp_path):
        """Test exclusions verify BOTH what's excluded AND included."""
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

        # Verify inclusions (critical - ensures we don't exclude everything)
        assert "keep.py" in paths
        assert "keep2.md" in paths

    def test_scanner_include_vcs(self, sample_files):
        """Test including VCS directories when explicitly requested."""
        scanner = FileScanner(sample_files, exclude_vcs=False)
        paths = list(scanner.scan())

        # .git directory should be included
        git_paths = [p for p in paths if ".git" in p.parts]
        assert len(git_paths) > 0

    def test_scanner_custom_exclusions(self, sample_files):
        """Test custom exclusion patterns."""
        scanner = FileScanner(sample_files, exclude_patterns=["*.txt"])
        paths = list(scanner.scan())

        # .txt files should be excluded
        txt_files = [p for p in paths if p.suffix == ".txt"]
        assert len(txt_files) == 0

        # Other files should be included
        py_files = [p for p in paths if p.suffix == ".py"]
        assert len(py_files) > 0

    def test_scanner_multiple_exclusions(self, sample_files):
        """Test multiple exclusion patterns."""
        scanner = FileScanner(sample_files, exclude_patterns=["*.txt", "*.py"])
        paths = list(scanner.scan())

        # Both .txt and .py files should be excluded
        txt_files = [p for p in paths if p.suffix == ".txt"]
        py_files = [p for p in paths if p.suffix == ".py"]
        assert len(txt_files) == 0
        assert len(py_files) == 0

    def test_scanner_directory_exclusions(self, sample_files):
        """Test excluding entire directories."""
        scanner = FileScanner(sample_files, exclude_patterns=["subdir1", "subdir1/*"])
        paths = list(scanner.scan())

        # subdir1 directory itself and files in subdir1 should be excluded
        subdir1_paths = [p for p in paths if "subdir1" in str(p)]
        assert len(subdir1_paths) == 0

    def test_scanner_deterministic_ordering(self, sample_files):
        """Test that scanner returns files in deterministic order."""
        scanner = FileScanner(sample_files)

        # Scan twice and compare order
        paths1 = [str(p.relative_to(sample_files)) for p in scanner.scan()]
        paths2 = [str(p.relative_to(sample_files)) for p in scanner.scan()]

        assert paths1 == paths2  # Same order every time

        # Should be lexicographically sorted
        assert paths1 == sorted(paths1)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_scanner_nonexistent_source(self, tmp_path):
        """Test error handling for nonexistent source."""
        scanner = FileScanner(tmp_path / "nonexistent")

        with pytest.raises(FileNotFoundError):
            list(scanner.scan())

    def test_scanner_file_not_directory(self, tmp_path):
        """Test error handling when source is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        scanner = FileScanner(file_path)

        with pytest.raises(NotADirectoryError):
            list(scanner.scan())


class TestEdgeCases:
    """Test edge cases and special scenarios."""

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
        """Test exclusion patterns with wildcards."""
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


class TestFileCount:
    """Test file counting functionality."""

    def test_count_files(self, sample_files):
        """Test counting files, dirs, and symlinks."""
        scanner = FileScanner(sample_files)
        counts = scanner.count_files()

        assert "files" in counts
        assert "dirs" in counts
        assert "symlinks" in counts
        assert "total" in counts

        assert counts["files"] > 0
        assert counts["total"] == (
            counts["files"] + counts["dirs"] + counts["symlinks"]
        )

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

    def test_count_with_exclusions(self, sample_files):
        """Test file counting respects exclusions."""
        scanner_all = FileScanner(sample_files, exclude_patterns=[])
        scanner_filtered = FileScanner(sample_files, exclude_patterns=["*.txt"])

        counts_all = scanner_all.count_files()
        counts_filtered = scanner_filtered.count_files()

        # Filtered count should be less
        assert counts_filtered["total"] < counts_all["total"]


class TestGitignoreSupport:
    """Test .gitignore file support."""

    def test_gitignore_basic(self, tmp_path):
        """Test basic .gitignore support."""
        # Create test structure
        (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__\n")
        (tmp_path / "file.py").write_text("code")
        (tmp_path / "file.pyc").write_text("compiled")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cache.pyc").write_text("cache")

        # Without respect_gitignore
        scanner_no = FileScanner(tmp_path, respect_gitignore=False)
        paths_no = list(scanner_no.scan())
        assert any("file.pyc" in str(p) for p in paths_no)

        # With respect_gitignore
        scanner_yes = FileScanner(tmp_path, respect_gitignore=True)
        paths_yes = list(scanner_yes.scan())
        assert not any("file.pyc" in str(p) for p in paths_yes)

    def test_gitignore_missing(self, tmp_path):
        """Test scanner works when .gitignore doesn't exist."""
        (tmp_path / "file.txt").write_text("content")

        scanner = FileScanner(tmp_path, respect_gitignore=True)
        paths = list(scanner.scan())

        assert len(paths) > 0  # Should still scan files


class TestEstimateSize:
    """Test size estimation functionality."""

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

    def test_estimate_size_multiple_files(self, tmp_path):
        """Test size estimation with text files."""
        (tmp_path / "file1.txt").write_text("a" * 100)
        (tmp_path / "file2.txt").write_text("b" * 200)
        (tmp_path / "file3.txt").write_text("c" * 300)

        scanner = FileScanner(tmp_path)
        total_size = scanner.estimate_size()

        # Should be sum of all file sizes (600 bytes)
        assert total_size == 600

    def test_estimate_size_excludes_symlinks(self, tmp_path):
        """Test that symlinks are not counted in size."""
        (tmp_path / "real.txt").write_text("content")
        (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")

        scanner = FileScanner(tmp_path)
        total_size = scanner.estimate_size()

        # Should only count real file, not symlink
        assert total_size == len("content")


class TestCollectFileMetadata:
    """Test metadata collection for manifest generation."""

    def test_collect_file_metadata(self, tmp_path):
        """Test collecting metadata for a regular file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("hello world")

        scanner = FileScanner(tmp_path)
        metadata = scanner.collect_file_metadata(file_path)

        assert metadata["path"] == "test.txt"
        assert metadata["type"] == FileType.FILE
        assert metadata["size"] == 11
        assert metadata["mode"].startswith("0")  # Octal mode
        assert "mtime_utc" in metadata
        assert metadata["link_target"] is None

    def test_collect_directory_metadata(self, tmp_path):
        """Test collecting metadata for a directory."""
        dir_path = tmp_path / "subdir"
        dir_path.mkdir()

        scanner = FileScanner(tmp_path)
        metadata = scanner.collect_file_metadata(dir_path)

        assert metadata["path"] == "subdir"
        assert metadata["type"] == FileType.DIR
        assert metadata["size"] is None  # Directories don't have size

    def test_collect_symlink_metadata(self, tmp_path):
        """Test collecting metadata for a symlink."""
        target = tmp_path / "target.txt"
        target.write_text("target content")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        scanner = FileScanner(tmp_path)
        metadata = scanner.collect_file_metadata(link)

        assert metadata["type"] == FileType.SYMLINK
        assert metadata["link_target"] is not None
        assert "target.txt" in metadata["link_target"]

    def test_metadata_includes_extended_fields(self, tmp_path):
        """Test that metadata includes fields for FILELIST.csv.gz."""
        file_path = tmp_path / "test.py"
        file_path.write_text("#!/usr/bin/env python\n")
        file_path.chmod(0o755)  # Make executable

        scanner = FileScanner(tmp_path)
        metadata = scanner.collect_file_metadata(file_path)

        # Check extended fields for FILELIST.csv.gz
        assert "_uid" in metadata
        assert "_gid" in metadata
        assert "_is_executable" in metadata
        assert metadata["_ext"] == "py"

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


class TestValidation:
    """Test validation and error handling."""

    def test_invalid_sha256_rejected(self):
        """Test that invalid SHA256 values are rejected."""
        with pytest.raises(ValueError, match="SHA256 must be 64 hexadecimal"):
            FileEntry(
                path="test.txt",
                type=FileType.FILE,
                size=100,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="invalid",
            )

    def test_invalid_mode_rejected(self):
        """Test that invalid mode values are rejected."""
        with pytest.raises(ValueError, match="Mode must be valid octal"):
            FileEntry(
                path="test.txt",
                type=FileType.FILE,
                size=100,
                mode="9999",  # 9 is not valid octal
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


class TestConvenienceFunction:
    """Test convenience scan_directory function."""

    def test_scan_directory(self, sample_files):
        """Test scan_directory convenience function."""
        paths = list(scan_directory(sample_files))

        assert len(paths) > 0
        # VCS should be excluded by default
        for path in paths:
            assert ".git" not in path.parts

    def test_scan_directory_with_options(self, sample_files):
        """Test scan_directory with custom options."""
        paths = list(
            scan_directory(
                sample_files,
                exclude_patterns=["*.txt"],
                exclude_vcs=False,
            )
        )

        # .txt files should be excluded
        txt_files = [p for p in paths if p.suffix == ".txt"]
        assert len(txt_files) == 0


class TestVCSDirectories:
    """Test VCS directory detection."""

    def test_all_vcs_directories_excluded(self, tmp_path):
        """Test that all default VCS directories are excluded."""
        # Create VCS directories
        for vcs_dir in DEFAULT_VCS_DIRS:
            (tmp_path / vcs_dir).mkdir()
            (tmp_path / vcs_dir / "file").write_text("vcs file")

        (tmp_path / "regular.txt").write_text("regular file")

        scanner = FileScanner(tmp_path, exclude_vcs=True)
        paths = list(scanner.scan())

        # Should find regular file
        assert any("regular.txt" in str(p) for p in paths)

        # Should not find any VCS directories
        for vcs_dir in DEFAULT_VCS_DIRS:
            assert not any(vcs_dir in p.parts for p in paths)

    def test_nested_vcs_directories(self, tmp_path):
        """Test that files inside nested VCS dirs are excluded."""
        nested = tmp_path / "project" / "src" / ".git" / "objects"
        nested.mkdir(parents=True)
        (nested / "abc123").write_text("git object")

        (tmp_path / "project" / "file.txt").write_text("project file")

        scanner = FileScanner(tmp_path, exclude_vcs=True)
        paths = list(scanner.scan())

        # Should find project file
        assert any("file.txt" in str(p) for p in paths)

        # Should not find anything in .git
        assert not any(".git" in p.parts for p in paths)


class TestScannerManifestIntegration:
    """Test end-to-end integration between Scanner and Manifest."""

    def test_scanner_to_fileentry_pipeline(self, tmp_path):
        """Test full pipeline: Scanner → metadata → FileEntry."""
        # Create test files with various types
        (tmp_path / "file.txt").write_text("content")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "script.py").write_text("#!/usr/bin/env python\n")
        (tmp_path / "script.py").chmod(0o755)

        scanner = FileScanner(tmp_path)

        # Collect metadata and create FileEntry objects
        file_entries = []
        for path in scanner.scan():
            metadata = scanner.collect_file_metadata(path)

            # Verify all paths are relative
            assert not Path(metadata["path"]).is_absolute(), (
                f"Scanner returned absolute path: {metadata['path']}"
            )

            # Create FileEntry (will validate schema)
            entry = FileEntry(
                path=metadata["path"],
                type=metadata["type"],
                size=metadata["size"],
                mode=metadata["mode"],
                mtime_utc=metadata["mtime_utc"],
                link_target=metadata["link_target"],
            )
            file_entries.append(entry)

        # Verify we got all expected files
        paths = [e.path for e in file_entries]
        assert "file.txt" in paths
        assert "subdir" in paths
        assert "script.py" in paths

        # Verify executable detection
        script_entry = next(e for e in file_entries if e.path == "script.py")
        assert script_entry.mode == "0755"

    def test_manifest_with_scanned_files(self, tmp_path):
        """Test creating complete manifest from scanned files."""
        from coldstore.core.manifest import (
            ColdstoreManifest,
            SourceMetadata,
            EnvironmentMetadata,
            SystemMetadata,
            ToolsMetadata,
            GitMetadata,
            ArchiveMetadata,
            MemberCount,
        )

        # Create test structure
        (tmp_path / "README.md").write_text("# Project")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        # Scan files
        scanner = FileScanner(tmp_path)
        file_entries = []

        for path in scanner.scan():
            metadata = scanner.collect_file_metadata(path)
            entry = FileEntry(
                path=metadata["path"],
                type=metadata["type"],
                size=metadata["size"],
                mode=metadata["mode"],
                mtime_utc=metadata["mtime_utc"],
            )
            file_entries.append(entry)

        # Create manifest
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="test-integration",
            source=SourceMetadata(root=str(tmp_path)),
            environment=EnvironmentMetadata(
                system=SystemMetadata(
                    os="Darwin", os_version="23.6.0", hostname="test"
                ),
                tools=ToolsMetadata(
                    coldstore_version="2.0.0", python_version="3.11.0"
                ),
            ),
            git=GitMetadata(present=False),
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="a" * 64,
                member_count=MemberCount(files=2, dirs=1),
            ),
            files=file_entries,
        )

        # Verify manifest serialization
        yaml_str = manifest.to_yaml()
        assert "README.md" in yaml_str
        assert "src/main.py" in yaml_str

        # Verify all paths in manifest are relative
        for file_entry in manifest.files:
            assert not Path(file_entry.path).is_absolute(), (
                f"Manifest contains absolute path: {file_entry.path}"
            )


class TestFixtureVerification:
    """Verify test fixture structure."""

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
