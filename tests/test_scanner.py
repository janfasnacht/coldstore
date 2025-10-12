"""Tests for file system scanner."""

import pytest

from coldstore.core.scanner import DEFAULT_VCS_DIRS, FileScanner, scan_directory


class TestFileScanner:
    """Test file scanner basic functionality."""

    def test_scanner_basic(self, sample_files):
        """Test basic file scanning."""
        scanner = FileScanner(sample_files)
        paths = list(scanner.scan())

        # Should find files but not .git directory by default
        assert len(paths) > 0
        assert any("file1.txt" in str(p) for p in paths)
        assert any("file2.py" in str(p) for p in paths)

    def test_scanner_excludes_vcs_by_default(self, sample_files):
        """Test that VCS directories are excluded by default."""
        scanner = FileScanner(sample_files, exclude_vcs=True)
        paths = list(scanner.scan())

        # .git directory and its contents should be excluded
        for path in paths:
            assert ".git" not in path.parts

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

    def test_scanner_deterministic_ordering(self, sample_files):
        """Test that scanner returns files in deterministic order."""
        scanner = FileScanner(sample_files)

        # Scan twice and compare order
        paths1 = [str(p.relative_to(sample_files)) for p in scanner.scan()]
        paths2 = [str(p.relative_to(sample_files)) for p in scanner.scan()]

        assert paths1 == paths2  # Same order every time

        # Should be lexicographically sorted
        assert paths1 == sorted(paths1)


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

    def test_estimate_size_basic(self, sample_files):
        """Test basic size estimation."""
        scanner = FileScanner(sample_files)
        total_size = scanner.estimate_size()

        # Should get total size of all files
        assert total_size > 0

    def test_estimate_size_multiple_files(self, tmp_path):
        """Test size estimation with known file sizes."""
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

        from coldstore.core.manifest import FileType

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

        from coldstore.core.manifest import FileType

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

        from coldstore.core.manifest import FileType

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
