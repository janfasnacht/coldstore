"""Tests for CLI functionality."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from coldstore.cli.main import main


class TestCLI:
    """Test command-line interface functionality."""

    def test_cli_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Coldstore" in result.output
        assert "SOURCE_PATH" in result.output
        assert "ARCHIVE_DIR" in result.output

    def test_cli_missing_arguments(self):
        """Test CLI with missing required arguments."""
        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 2
        assert "Missing argument" in result.output

    def test_cli_basic_archive(self):
        """Test basic CLI archiving."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create source directory
            source_dir = tmp_path / "source"
            source_dir.mkdir()
            (source_dir / "file.txt").write_text("test content")

            # Create archive directory
            archive_dir = tmp_path / "archives"

            # Run CLI
            result = runner.invoke(
                main, [str(source_dir), str(archive_dir), "--note", "CLI test"]
            )

            assert result.exit_code == 0
            assert "📊 Collecting metadata" in result.output
            assert "✅ Archive created" in result.output

            # Verify files created
            assert len(list(archive_dir.glob("*.tar.gz"))) == 1
            assert len(list(archive_dir.glob("*.sha256"))) == 1
            assert len(list(archive_dir.glob("*.README.md"))) == 1

    def test_cli_custom_name(self):
        """Test CLI with custom archive name."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            (source_dir / "file.txt").write_text("test")

            archive_dir = tmp_path / "archives"

            result = runner.invoke(
                main, [str(source_dir), str(archive_dir), "--name", "custom-cli-test"]
            )

            assert result.exit_code == 0
            assert (archive_dir / "custom-cli-test.tar.gz").exists()

    def test_cli_no_archive(self):
        """Test CLI with --no-archive flag."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            (source_dir / "file.txt").write_text("test")

            archive_dir = tmp_path / "archives"

            result = runner.invoke(
                main, [str(source_dir), str(archive_dir), "--no-archive"]
            )

            assert result.exit_code == 0
            assert len(list(archive_dir.glob("*.tar.gz"))) == 0
            assert len(list(archive_dir.glob("*.README.md"))) == 1

    def test_cli_exclude_patterns(self):
        """Test CLI with multiple exclude patterns."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            (source_dir / "keep.txt").write_text("keep")
            (source_dir / "exclude.log").write_text("exclude")
            (source_dir / "exclude.tmp").write_text("exclude")

            archive_dir = tmp_path / "archives"

            result = runner.invoke(
                main,
                [
                    str(source_dir),
                    str(archive_dir),
                    "--exclude",
                    "*.log",
                    "--exclude",
                    "*.tmp",
                ],
            )

            assert result.exit_code == 0
            assert "Excluding:" in result.output

    def test_cli_compression_level(self):
        """Test CLI with different compression levels."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            (source_dir / "file.txt").write_text("content")

            archive_dir = tmp_path / "archives"

            result = runner.invoke(
                main, [str(source_dir), str(archive_dir), "--compress-level", "9"]
            )

            assert result.exit_code == 0

    def test_cli_upload_validation(self):
        """Test CLI upload flag validation."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            (source_dir / "file.txt").write_text("test")

            archive_dir = tmp_path / "archives"

            # Should fail without remote-path
            result = runner.invoke(
                main, [str(source_dir), str(archive_dir), "--upload"]
            )

            assert result.exit_code == 1
            assert "--upload requires --remote-path" in result.output

    def test_cli_nonexistent_source(self):
        """Test CLI with nonexistent source directory."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            nonexistent = tmp_path / "nonexistent"
            archive_dir = tmp_path / "archives"

            result = runner.invoke(main, [str(nonexistent), str(archive_dir)])

            assert result.exit_code == 2  # Click validation error
            assert "does not exist" in result.output

    def test_cli_force_flag(self):
        """Test CLI with force flag."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            (source_dir / "file.txt").write_text("test")

            archive_dir = tmp_path / "archives"

            result = runner.invoke(main, [str(source_dir), str(archive_dir), "--force"])

            assert result.exit_code == 0
