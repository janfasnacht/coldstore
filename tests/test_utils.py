"""Tests for utility functions."""

from coldstore.core.metadata import get_metadata
from coldstore.utils.file_ops import file_tree_fallback, get_file_tree
from coldstore.utils.formatters import generate_readme, get_human_size


class TestFormatters:
    """Test formatting utility functions."""

    def test_get_human_size(self):
        """Test human-readable size formatting."""
        # Updated to match new format_size implementation (consistent spacing)
        assert get_human_size(0) == "0 B"
        assert get_human_size(512) == "512 B"
        assert get_human_size(1024) == "1.0 KB"
        assert get_human_size(1024 * 1024) == "1.0 MB"
        assert get_human_size(1024 * 1024 * 1024) == "1.0 GB"
        assert get_human_size(1536) == "1.5 KB"  # 1.5 KB

    def test_generate_readme(self):
        """Test README generation."""
        meta = {
            "file_count": 5,
            "directory_count": 2,
            "total_size_human": "1.23 MB",
            "earliest_date": "2023-01-01 10:00:00",
            "latest_date": "2023-12-31 15:30:00",
            "top_file_types": [(".txt", 3), (".py", 2)],
            "largest_files": [
                ("big_file.txt", "500.00 KB"),
                ("medium.py", "200.00 KB"),
            ],
            "system_info": {
                "username": "testuser",
                "hostname": "testhost",
                "os": "TestOS",
            },
            "archive_date": "2023-06-15 12:00:00",
        }

        readme = generate_readme(
            base_name="test-archive",
            source_name="test_project",
            source_path="/path/to/test_project",
            timestamp="2023-06-15",
            meta=meta,
            file_tree="test_project/\n├── file1.txt\n└── file2.py",
            sha256_hash="abcd1234",
            note="Test note",
        )

        # Verify key sections are present
        assert "# Archive: test-archive" in readme
        assert "## Source Information" in readme
        assert "## Contents Summary" in readme
        assert "## Notes" in readme
        assert "Test note" in readme
        assert "## File Types" in readme
        assert "## Largest Files" in readme
        assert "## Directory Structure" in readme
        assert "testuser" in readme
        assert "testhost" in readme
        assert "abcd1234" in readme

    def test_generate_readme_minimal(self):
        """Test README generation with minimal metadata."""
        meta = {
            "file_count": 1,
            "directory_count": 0,
            "total_size_human": "10.00 B",
            "earliest_date": "N/A",
            "latest_date": "N/A",
            "top_file_types": [],
            "largest_files": [],
            "system_info": {},
            "archive_date": "2023-06-15 12:00:00",
        }

        readme = generate_readme(
            base_name="minimal",
            source_name="minimal",
            source_path="/path/to/minimal",
            timestamp="2023-06-15",
            meta=meta,
            file_tree="minimal/\n└── file.txt",
        )

        assert "# Archive: minimal" in readme
        assert "(No additional notes provided)" in readme


class TestFileOps:
    """Test file operation utilities."""

    def test_file_tree_fallback(self, tmp_path):
        """Test Python fallback file tree generation."""
        # Create test structure
        test_dir = tmp_path / "test_tree"
        test_dir.mkdir()

        (test_dir / "file1.txt").write_text("content")
        sub_dir = test_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "file2.py").write_text("code")
        (sub_dir / "nested").mkdir()
        (sub_dir / "nested" / "deep.json").write_text("{}")

        # Generate tree
        tree = file_tree_fallback(test_dir, max_depth=2)

        assert "test_tree" in tree
        assert "file1.txt" in tree
        assert "subdir" in tree
        assert "file2.py" in tree
        assert "nested" in tree
        # deep.json should not appear at depth 2
        assert "deep.json" not in tree

    def test_file_tree_fallback_empty(self, tmp_path):
        """Test file tree for empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        tree = file_tree_fallback(empty_dir)
        assert "empty" in tree

    def test_file_tree_fallback_depth_zero(self, tmp_path):
        """Test file tree with zero depth."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        tree = file_tree_fallback(test_dir, max_depth=0)
        assert "test" in tree
        assert "file.txt" in tree  # Files at current level are shown
        # But subdirectories won't be recursed into at depth 0

    def test_get_file_tree_fallback_when_tree_unavailable(self, tmp_path):
        """Test that get_file_tree falls back to Python implementation."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        # This should work even if 'tree' command is not available
        tree = get_file_tree(test_dir)
        assert "test" in tree or "file.txt" in tree  # Either tree output or fallback


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_permission_denied_simulation(self, tmp_path):
        """Test handling of permission denied scenarios."""
        # This is tricky to test reliably across platforms
        # For now, just test that the fallback handles the case gracefully

        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # The fallback should handle permission errors gracefully
        tree = file_tree_fallback(test_dir)
        assert isinstance(tree, str)

    def test_unicode_filenames(self, tmp_path):
        """Test handling of unicode filenames."""
        test_dir = tmp_path / "unicode_test"
        test_dir.mkdir()

        # Create files with unicode names
        (test_dir / "файл.txt").write_text("content")
        (test_dir / "测试.py").write_text("code")
        (test_dir / "🎉.json").write_text("{}")

        meta = get_metadata(test_dir)
        assert meta["file_count"] == 3

        tree = file_tree_fallback(test_dir)
        assert isinstance(tree, str)

    def test_very_long_paths(self, tmp_path):
        """Test handling of very long paths."""
        # Create a deeply nested structure
        current_dir = tmp_path / "long_path_test"
        current_dir.mkdir()

        # Create a reasonably deep structure (not too deep to avoid OS limits)
        for i in range(5):
            current_dir = current_dir / f"level_{i}"
            current_dir.mkdir()

        (current_dir / "deep_file.txt").write_text("deep content")

        meta = get_metadata(tmp_path / "long_path_test")
        assert meta["file_count"] == 1
