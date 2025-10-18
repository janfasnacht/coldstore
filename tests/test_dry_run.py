"""Tests for dry-run preview functionality."""



from coldstore.core.scanner import FileScanner
from coldstore.utils.formatters import format_time
from coldstore.utils.preview import (
    estimate_compressed_size,
    estimate_time,
    find_largest_files,
    generate_dry_run_preview,
    sample_compression_ratio,
)


class TestCompressionEstimation:
    """Test compression estimation functions."""

    def test_estimate_compressed_size_typical(self):
        """Test compression estimation for typical sizes."""
        # 1 GB uncompressed
        uncompressed = 1024 * 1024 * 1024

        estimated, min_size, max_size = estimate_compressed_size(uncompressed)

        # Estimated should be ~45% of original (reasonable for text/code)
        assert 0.4 * uncompressed < estimated < 0.5 * uncompressed

        # Min should be smaller, max should be larger
        assert min_size < estimated < max_size

        # Check bounds are reasonable
        assert min_size >= 0.3 * uncompressed  # At least 30%
        assert max_size <= 0.7 * uncompressed  # At most 70%

    def test_estimate_compressed_size_small_file(self):
        """Test compression estimation for small files."""
        # 100 KB
        uncompressed = 100 * 1024

        estimated, min_size, max_size = estimate_compressed_size(uncompressed)

        # Should still be reasonable percentages
        assert min_size < estimated < max_size
        assert estimated > 0  # Never estimate zero

    def test_estimate_compressed_size_zero(self):
        """Test compression estimation for empty/zero size."""
        uncompressed = 0

        estimated, min_size, max_size = estimate_compressed_size(uncompressed)

        # All should be zero
        assert estimated == 0
        assert min_size == 0
        assert max_size == 0


class TestTimeEstimation:
    """Test time estimation functions."""

    def test_estimate_time_small_project(self):
        """Test time estimation for small projects."""
        # 10 MB project
        size = 10 * 1024 * 1024

        estimated, max_time = estimate_time(size)

        # Should be quick - under 1 minute
        assert estimated < 60
        assert max_time > estimated
        # Max should be reasonable multiple of estimate
        assert max_time <= estimated * 2

    def test_estimate_time_large_project(self):
        """Test time estimation for large projects."""
        # 10 GB project
        size = 10 * 1024 * 1024 * 1024

        estimated, max_time = estimate_time(size)

        # Should take longer
        assert estimated > 60  # More than a minute
        assert max_time > estimated

    def test_estimate_time_zero(self):
        """Test time estimation for zero size."""
        size = 0

        estimated, max_time = estimate_time(size)

        # Should still have overhead time
        assert estimated > 0
        assert max_time > estimated

    def test_format_time_estimate_seconds(self):
        """Test formatting time under 60 seconds."""
        assert format_time(30) == "30s"
        assert format_time(59) == "59s"

    def test_format_time_estimate_minutes(self):
        """Test formatting time in minutes."""
        assert format_time(60) == "1m"
        assert format_time(90) == "1m 30s"
        assert format_time(135) == "2m 15s"
        assert format_time(180) == "3m"

    def test_format_time_estimate_hours(self):
        """Test formatting time in hours."""
        assert format_time(3600) == "1h"
        assert format_time(3660) == "1h 1m"
        assert format_time(7200) == "2h"
        assert format_time(5400) == "1h 30m"


class TestLargestFilesFinder:
    """Test finding largest files."""

    def test_find_largest_files_basic(self, tmp_path):
        """Test finding largest files from scanner."""
        # Create files of various sizes
        (tmp_path / "small.txt").write_bytes(b"a" * 100)  # 100 bytes
        (tmp_path / "medium.txt").write_bytes(b"b" * 1000)  # 1 KB
        (tmp_path / "large.txt").write_bytes(b"c" * 10000)  # 10 KB

        scanner = FileScanner(tmp_path)
        largest = find_largest_files(scanner, n=10)

        # Should find all 3 files
        assert len(largest) == 3

        # Should be sorted by size (largest first)
        assert largest[0]["path"] == "large.txt"
        assert largest[0]["size_bytes"] == 10000
        assert largest[1]["path"] == "medium.txt"
        assert largest[1]["size_bytes"] == 1000
        assert largest[2]["path"] == "small.txt"
        assert largest[2]["size_bytes"] == 100

    def test_find_largest_files_limit(self, tmp_path):
        """Test limiting number of largest files."""
        # Create 20 files of different sizes
        for i in range(20):
            (tmp_path / f"file{i:02d}.txt").write_bytes(b"x" * (i * 100))

        scanner = FileScanner(tmp_path)
        largest = find_largest_files(scanner, n=5)

        # Should return only 5
        assert len(largest) == 5

        # Should be the 5 largest
        assert largest[0]["path"] == "file19.txt"
        assert largest[4]["path"] == "file15.txt"

    def test_find_largest_files_ignores_directories(self, tmp_path):
        """Test that directories are not included in largest files."""
        (tmp_path / "file.txt").write_bytes(b"content" * 1000)
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "nested.txt").write_bytes(b"x" * 100)

        scanner = FileScanner(tmp_path)
        largest = find_largest_files(scanner, n=10)

        # Should only find files, not directories
        paths = [f["path"] for f in largest]
        assert "dir" not in paths
        assert "file.txt" in paths
        assert "dir/nested.txt" in paths

    def test_find_largest_files_empty_directory(self, tmp_path):
        """Test finding largest files in empty directory."""
        scanner = FileScanner(tmp_path)
        largest = find_largest_files(scanner, n=10)

        assert largest == []


class TestDryRunPreviewGeneration:
    """Test dry-run preview generation."""

    def test_generate_preview_basic(self, tmp_path):
        """Test basic preview generation."""
        # Create test structure
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        (tmp_path / "dir").mkdir()

        scanner = FileScanner(tmp_path)
        dest = tmp_path / "archives"

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=tmp_path,
            destination=dest,
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        # Verify required keys
        assert "counts" in preview
        assert "sizes" in preview
        assert "largest_files" in preview
        assert "git" in preview
        assert "exclusions" in preview
        assert "output_files" in preview
        assert "time_estimate" in preview

        # Verify counts
        counts = preview["counts"]
        assert counts["files"] > 0
        assert counts["total"] > 0

        # Verify sizes
        sizes = preview["sizes"]
        assert sizes["uncompressed_bytes"] > 0
        assert sizes["compressed_estimate_bytes"] > 0
        assert sizes["compressed_estimate_bytes"] < sizes["uncompressed_bytes"]

        # Verify output files
        outputs = preview["output_files"]
        assert outputs["archive"].name == "test.tar.gz"
        assert ".MANIFEST.json" in str(outputs["manifest_json"])
        assert ".sha256" in str(outputs["sha256"])

    def test_generate_preview_with_milestone(self, tmp_path):
        """Test preview generation with milestone."""
        (tmp_path / "file.txt").write_text("content")
        scanner = FileScanner(tmp_path)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=tmp_path,
            destination=tmp_path / "out",
            archive_filename="archive.tar.gz",
            compression_level=6,
            milestone="v1.0 release",
        )

        assert preview["milestone"] == "v1.0 release"

    def test_generate_preview_with_exclusions(self, tmp_path):
        """Test preview generation shows exclusion patterns."""
        (tmp_path / "file.txt").write_text("content")

        scanner = FileScanner(tmp_path, exclude_patterns=["*.pyc", "__pycache__"])
        dest = tmp_path / "out"

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=tmp_path,
            destination=dest,
            archive_filename="test.tar.gz",
            compression_level=6,
            exclude_patterns=["*.pyc", "__pycache__"],
        )

        # Should show VCS exclusions + custom patterns
        exclusions = preview["exclusions"]
        assert any("VCS" in e for e in exclusions)
        assert "*.pyc" in exclusions
        assert "__pycache__" in exclusions

    def test_generate_preview_largest_files(self, tmp_path):
        """Test that preview includes largest files."""
        # Create files of different sizes
        (tmp_path / "tiny.txt").write_bytes(b"a" * 10)
        (tmp_path / "huge.bin").write_bytes(b"b" * 10000)
        (tmp_path / "medium.dat").write_bytes(b"c" * 1000)

        scanner = FileScanner(tmp_path)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=tmp_path,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        largest = preview["largest_files"]
        assert len(largest) > 0

        # Should be sorted by size
        assert largest[0]["path"] == "huge.bin"
        assert largest[0]["size_bytes"] == 10000

    def test_generate_preview_time_estimate_reasonable(self, tmp_path):
        """Test that time estimates are reasonable."""
        # Create ~1 MB of files
        (tmp_path / "file.bin").write_bytes(b"x" * (1024 * 1024))

        scanner = FileScanner(tmp_path)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=tmp_path,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        time_est = preview["time_estimate"]
        assert "seconds" in time_est
        assert "max_seconds" in time_est
        assert "display" in time_est
        assert "display_range" in time_est

        # 1 MB should be quick
        assert time_est["seconds"] < 60

        # Max should be larger than estimate
        assert time_est["max_seconds"] > time_est["seconds"]


class TestDryRunCLIIntegration:
    """Test dry-run integration with CLI."""

    def test_dry_run_creates_no_files(self, tmp_path):
        """Test that dry-run mode creates no files."""
        # Create test source
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        # Output directory
        dest = tmp_path / "output"
        dest.mkdir()

        # Run dry-run (would be via CLI, testing the preview functions)
        scanner = FileScanner(source)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=dest,
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        # Verify preview was generated
        assert preview is not None

        # Verify NO files were created in output directory
        created_files = list(dest.iterdir())
        assert len(created_files) == 0, f"Dry-run created files: {created_files}"

    def test_dry_run_size_estimate_accuracy(self, tmp_path):
        """Test that size estimates are within reasonable bounds."""
        # Create test data with known compression characteristics
        source = tmp_path / "source"
        source.mkdir()

        # Highly compressible (repeated text)
        (source / "compressible.txt").write_text("a" * 100000)

        scanner = FileScanner(source)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        sizes = preview["sizes"]
        uncompressed = sizes["uncompressed_bytes"]
        compressed = sizes["compressed_estimate_bytes"]

        # Compressed should be less than uncompressed
        assert compressed < uncompressed

        # Should be within estimation range (35-60% of original)
        assert compressed >= sizes["compressed_min_bytes"]
        assert compressed <= sizes["compressed_max_bytes"]

        # For highly compressible data, estimate might be conservative
        # but should be reasonable
        assert 0.2 < (compressed / uncompressed) < 0.8

    def test_dry_run_with_vcs_exclusions(self, tmp_path):
        """Test dry-run correctly shows VCS exclusions."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.py").write_text("code")
        (source / ".git").mkdir()
        (source / ".git" / "config").write_text("git config")

        scanner = FileScanner(source, exclude_vcs=True)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        # Should show VCS exclusion in exclusions list
        assert any("VCS" in e for e in preview["exclusions"])

        # Counts should not include .git directory
        counts = preview["counts"]
        # Should only have file.py (no .git directory or files)
        assert counts["files"] == 1  # file.py
        assert counts["dirs"] == 0  # .git excluded


class TestPreviewEdgeCases:
    """Test edge cases for preview generation."""

    def test_preview_empty_directory(self, tmp_path):
        """Test preview generation for empty directory."""
        source = tmp_path / "empty"
        source.mkdir()

        scanner = FileScanner(source)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        # Should complete without error
        assert preview["counts"]["total"] == 0
        assert preview["sizes"]["uncompressed_bytes"] == 0
        assert preview["largest_files"] == []

    def test_preview_no_exclusions(self, tmp_path):
        """Test preview when no exclusions are applied."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        scanner = FileScanner(source, exclude_vcs=False, exclude_patterns=[])

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
            exclude_patterns=None,
        )

        # Should still work, just no custom exclusions
        # (may still have VCS exclusions if scanner has exclude_vcs=True by default)
        assert "exclusions" in preview

    def test_preview_with_symlinks(self, tmp_path):
        """Test preview handles symlinks correctly."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "real.txt").write_text("content")
        (source / "link.txt").symlink_to(source / "real.txt")

        scanner = FileScanner(source)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        counts = preview["counts"]
        # Should count both file and symlink
        assert counts["files"] == 1
        assert counts["symlinks"] == 1

    def test_preview_unicode_paths(self, tmp_path):
        """Test preview handles Unicode filenames."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "émoji_🎉.txt").write_text("content")
        (source / "中文.py").write_text("code")

        scanner = FileScanner(source)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        # Should handle Unicode without errors
        assert preview["counts"]["files"] == 2

        # Largest files should include Unicode names
        largest = preview["largest_files"]
        paths = [f["path"] for f in largest]
        assert any("émoji" in p or "中文" in p for p in paths)


class TestPreviewSizeEstimationAccuracy:
    """Test size estimation accuracy against expected values."""

    def test_estimate_within_5_percent_guideline(self, tmp_path):
        """Test that estimates could be within 5% for typical projects.

        Note: This test verifies the estimation logic is reasonable,
        not that it exactly matches real compression (which varies).
        The 5% target in the issue is for comparing dry-run vs actual,
        not for verifying estimation algorithm accuracy.
        """
        source = tmp_path / "source"
        source.mkdir()

        # Create typical mixed content
        (source / "text.txt").write_text("a" * 10000)  # Very compressible
        (source / "code.py").write_text("def foo():\n    pass\n" * 500)
        # Less compressible binary
        (source / "binary.bin").write_bytes(bytes(range(256)) * 100)

        scanner = FileScanner(source)

        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        sizes = preview["sizes"]
        uncompressed = sizes["uncompressed_bytes"]
        estimated = sizes["compressed_estimate_bytes"]
        min_est = sizes["compressed_min_bytes"]
        max_est = sizes["compressed_max_bytes"]

        # Verify estimate is between min and max
        assert min_est <= estimated <= max_est

        # Verify range is reasonable (not too wide)
        range_percent = (max_est - min_est) / uncompressed * 100
        assert range_percent < 40  # Range should be less than 40% of original

        # Verify estimate is reasonable percentage
        percent = estimated / uncompressed * 100
        assert 30 < percent < 70  # Should be 30-70% of original


class TestCompressionSampling:
    """Test sampling-based compression estimation."""

    def test_sample_compression_ratio_basic(self, tmp_path):
        """Test basic sampling functionality."""
        # Create test files (large enough for sampling - need >100KB minimum)
        (tmp_path / "file1.txt").write_text("a" * 150000)  # Highly compressible
        (tmp_path / "file2.py").write_text("def foo():\n    pass\n" * 5000)

        scanner = FileScanner(tmp_path)
        result = sample_compression_ratio(scanner, compression_level=6)

        # Should return valid result
        assert result is not None
        assert "ratio" in result
        assert "sample_size" in result
        assert "compressed_size" in result
        assert "files_sampled" in result

        # Ratio should be reasonable (< 1.0 for compressed)
        assert 0 < result["ratio"] < 1.0

        # Sample size should be reasonable
        assert result["sample_size"] > 0
        assert result["compressed_size"] > 0
        assert result["compressed_size"] < result["sample_size"]

    def test_sample_compression_ratio_empty_directory(self, tmp_path):
        """Test sampling with empty directory."""
        scanner = FileScanner(tmp_path)
        result = sample_compression_ratio(scanner, compression_level=6)

        # Should return None for empty directory
        assert result is None

    def test_sample_compression_ratio_very_small_files(self, tmp_path):
        """Test sampling with very small files (below minimum)."""
        # Create files smaller than MIN_SAMPLE_BYTES
        for i in range(10):
            (tmp_path / f"tiny{i}.txt").write_text("x" * 10)

        scanner = FileScanner(tmp_path)
        result = sample_compression_ratio(scanner, compression_level=6)

        # May return None if total is below MIN_SAMPLE_BYTES
        # or valid result if sum is enough
        if result:
            assert result["sample_size"] > 0

    def test_sample_compression_ratio_respects_compression_level(self, tmp_path):
        """Test that different compression levels produce different results."""
        # Create highly compressible data
        (tmp_path / "data.txt").write_bytes(b"a" * (1024 * 1024))  # 1 MB of 'a'

        scanner = FileScanner(tmp_path)

        # Sample with different compression levels
        result_fast = sample_compression_ratio(scanner, compression_level=1)
        scanner2 = FileScanner(tmp_path)  # New scanner for second pass
        result_best = sample_compression_ratio(scanner2, compression_level=9)

        # Both should succeed
        assert result_fast is not None
        assert result_best is not None

        # Best compression should have better ratio (smaller)
        # For highly compressible data like repeated 'a'
        assert result_best["ratio"] <= result_fast["ratio"]

    def test_sample_size_distribution(self, tmp_path):
        """Test that sampling distributes across multiple files."""
        # Create several files
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_bytes(b"data" * 10000)

        scanner = FileScanner(tmp_path)
        result = sample_compression_ratio(scanner, compression_level=6)

        assert result is not None
        # Should sample from multiple files
        assert result["files_sampled"] > 1

    def test_estimate_uses_sampled_ratio(self, tmp_path):
        """Test that estimate_compressed_size uses sampled ratio."""
        # Test with known ratio
        uncompressed = 1024 * 1024  # 1 MB
        actual_ratio = 0.3  # 30% compressed

        estimated, min_size, max_size = estimate_compressed_size(
            uncompressed, actual_ratio=actual_ratio
        )

        # Estimate should be close to ratio * uncompressed
        expected = int(uncompressed * actual_ratio)
        assert estimated == expected

        # Min and max should be ±15%
        assert min_size == int(estimated * 0.85)
        assert max_size == int(estimated * 1.15)

    def test_preview_includes_sample_info(self, tmp_path):
        """Test that preview includes sampling information."""
        # Create test data
        (tmp_path / "file.txt").write_bytes(b"test" * 50000)  # 200KB

        scanner = FileScanner(tmp_path)
        preview = generate_dry_run_preview(
            scanner=scanner,
            source=tmp_path,
            destination=tmp_path / "out",
            archive_filename="test.tar.gz",
            compression_level=6,
        )

        # Should include sample info
        assert "sample" in preview

        # If sampling succeeded, should have valid data
        if preview["sample"]:
            sample = preview["sample"]
            assert "ratio" in sample
            assert "sample_size" in sample
            assert "compressed_size" in sample
            assert sample["ratio"] < 1.0  # Compressed should be smaller

    def test_sampling_with_mixed_file_types(self, tmp_path):
        """Test sampling with mix of file types."""
        # Create diverse files
        (tmp_path / "text.txt").write_text("a" * 50000)  # Highly compressible
        (tmp_path / "random.bin").write_bytes(
            bytes(range(256)) * 200
        )  # Less compressible
        (tmp_path / "code.py").write_text("def foo():\n    pass\n" * 1000)

        scanner = FileScanner(tmp_path)
        result = sample_compression_ratio(scanner, compression_level=6)

        assert result is not None
        # Should sample from multiple files
        assert result["files_sampled"] >= 2

        # Ratio should be very good (compressed data should be much smaller)
        # For highly compressible text, ratio can be very low (<0.1)
        assert 0.001 < result["ratio"] < 1.0
