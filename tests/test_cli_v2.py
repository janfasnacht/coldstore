"""Tests for Typer-based CLI."""


from typer.testing import CliRunner

from coldstore.cli.app import app


class TestCLIStructure:
    """Test CLI structure and basic functionality."""

    def test_app_help(self):
        """Test main app help output."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "coldstore" in result.output.lower()
        assert "freeze" in result.output
        assert "Event-driven project archival" in result.output

    def test_version_flag(self):
        """Test --version flag."""
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "coldstore v1.0.0-dev" in result.output

    def test_freeze_command_exists(self):
        """Test freeze command is available."""
        runner = CliRunner()
        result = runner.invoke(app, ["freeze", "--help"])

        assert result.exit_code == 0
        assert "freeze" in result.output.lower()
        assert "SOURCE" in result.output
        assert "DESTINATION" in result.output

    def test_freeze_help_shows_all_options(self):
        """Test freeze help shows all expected options."""
        runner = CliRunner()
        result = runner.invoke(app, ["freeze", "--help"])

        assert result.exit_code == 0

        # Event metadata options
        assert "--milestone" in result.output
        assert "--note" in result.output
        assert "--contact" in result.output

        # Output control
        assert "--compression-level" in result.output
        assert "--name" in result.output

        # Filtering
        assert "--exclude" in result.output

        # Advanced toggles
        assert "--no-manifest" in result.output
        assert "--no-filelist" in result.output
        assert "--no-sha256" in result.output

        # Runtime (--log-level is hidden, so not in help)

    def test_freeze_requires_arguments(self):
        """Test freeze requires SOURCE and DESTINATION."""
        runner = CliRunner()
        result = runner.invoke(app, ["freeze"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestCLIParameters:
    """Test CLI parameter handling."""

    def test_freeze_basic_parameters(self, tmp_path):
        """Test freeze with basic parameters."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        result = runner.invoke(app, ["freeze", str(source), str(dest)])

        assert result.exit_code == 0
        assert "Source:" in result.output
        assert "Destination:" in result.output
        assert "✅ Archive created successfully!" in result.output

    def test_freeze_with_milestone(self, tmp_path):
        """Test freeze with milestone parameter."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        result = runner.invoke(
            app,
            ["freeze", str(source), str(dest), "--milestone", "PNAS submission"],
        )

        assert result.exit_code == 0
        assert "Event:       PNAS submission" in result.output

    def test_freeze_with_multiple_notes(self, tmp_path):
        """Test freeze with multiple notes."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        result = runner.invoke(
            app,
            [
                "freeze",
                str(source),
                str(dest),
                "--note",
                "First note",
                "--note",
                "Second note",
            ],
        )

        assert result.exit_code == 0
        # Notes are stored in manifest but not displayed in summary
        assert "✅ Archive created successfully!" in result.output

    def test_freeze_with_contacts(self, tmp_path):
        """Test freeze with contact information."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        result = runner.invoke(
            app,
            [
                "freeze",
                str(source),
                str(dest),
                "--contact",
                "Jane Doe <jane@example.com>",
            ],
        )

        assert result.exit_code == 0
        # Contacts are stored in manifest but not displayed in summary
        assert "✅ Archive created successfully!" in result.output

    def test_freeze_compression_levels(self, tmp_path):
        """Test freeze with different compression levels."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        # Test level 1
        result = runner.invoke(
            app, ["freeze", str(source), str(dest), "--compression-level", "1"]
        )
        assert result.exit_code == 0
        assert "Compression: Level 1" in result.output

        # Test level 9
        result = runner.invoke(
            app, ["freeze", str(source), str(dest), "--compression-level", "9"]
        )
        assert result.exit_code == 0
        assert "Compression: Level 9" in result.output

    def test_freeze_with_exclusions(self, tmp_path):
        """Test freeze with exclusion patterns."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        result = runner.invoke(
            app,
            [
                "freeze",
                str(source),
                str(dest),
                "--exclude",
                "*.log",
                "--exclude",
                "*.tmp",
            ],
        )

        assert result.exit_code == 0
        assert "Exclusions:  2 pattern(s)" in result.output

    def test_freeze_with_custom_name(self, tmp_path):
        """Test freeze with custom archive name."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        result = runner.invoke(
            app,
            ["freeze", str(source), str(dest), "--name", "my_custom_archive"],
        )

        assert result.exit_code == 0
        # Name is not displayed in Step 1, but should be accepted without error

    def test_freeze_metadata_toggles(self, tmp_path):
        """Test freeze with metadata generation disabled."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        result = runner.invoke(
            app,
            [
                "freeze",
                str(source),
                str(dest),
                "--no-manifest",
                "--no-filelist",
                "--no-sha256",
            ],
        )

        assert result.exit_code == 0
        assert "Disabled:    MANIFEST, FILELIST, SHA256" in result.output

    def test_freeze_log_levels(self, tmp_path):
        """Test freeze with different log levels."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        # Test valid log levels
        for level in ["debug", "info", "warn", "error"]:
            result = runner.invoke(
                app, ["freeze", str(source), str(dest), "--log-level", level]
            )
            assert result.exit_code == 0

    def test_freeze_invalid_log_level(self, tmp_path):
        """Test freeze with invalid log level."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        result = runner.invoke(
            app, ["freeze", str(source), str(dest), "--log-level", "invalid"]
        )

        assert result.exit_code == 1
        assert "Invalid log level" in result.output

    def test_freeze_compression_level_out_of_range(self, tmp_path):
        """Test freeze with invalid compression level."""
        runner = CliRunner()
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        # Test level too high
        result = runner.invoke(
            app, ["freeze", str(source), str(dest), "--compression-level", "10"]
        )
        assert result.exit_code != 0

        # Test level too low
        result = runner.invoke(
            app, ["freeze", str(source), str(dest), "--compression-level", "0"]
        )
        assert result.exit_code != 0


class TestCLIIntegration:
    """Integration tests for end-to-end archiving workflow."""

    def test_freeze_creates_archive(self, tmp_path):
        """Test that freeze actually creates a working archive."""
        runner = CliRunner()

        # Create source with some files
        source = tmp_path / "source"
        source.mkdir()
        (source / "file1.txt").write_text("Hello world")
        (source / "file2.txt").write_text("Goodbye world")
        subdir = source / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("Nested file")

        dest = tmp_path / "dest"

        result = runner.invoke(app, ["freeze", str(source), str(dest)])

        assert result.exit_code == 0
        assert "✅ Archive created successfully!" in result.output

        # Check that archive was created
        archives = list(dest.glob("coldstore_*.tar.gz"))
        assert len(archives) == 1

        archive_path = archives[0]
        assert archive_path.exists()
        assert archive_path.stat().st_size > 0

    def test_freeze_with_manifest_and_filelist(self, tmp_path):
        """Test that MANIFEST and FILELIST files are created."""
        runner = CliRunner()

        source = tmp_path / "source"
        source.mkdir()
        (source / "test.txt").write_text("Test content")

        dest = tmp_path / "dest"

        result = runner.invoke(app, ["freeze", str(source), str(dest)])

        assert result.exit_code == 0

        # Check for MANIFEST.json sidecar
        manifests = list(dest.glob("*.MANIFEST.json"))
        assert len(manifests) == 1
        assert manifests[0].exists()

        # Check for SHA256 checksum file
        sha256_files = list(dest.glob("*.sha256"))
        assert len(sha256_files) == 1
        assert sha256_files[0].exists()

        # Verify MANIFEST.json contains expected fields
        import json

        manifest_data = json.loads(manifests[0].read_text())
        assert "manifest_version" in manifest_data
        assert "created_utc" in manifest_data
        assert "source" in manifest_data
        assert "archive" in manifest_data
        assert "environment" in manifest_data

    def test_freeze_with_exclusions(self, tmp_path):
        """Test that exclusion patterns work correctly."""
        runner = CliRunner()

        source = tmp_path / "source"
        source.mkdir()
        (source / "keep.txt").write_text("Keep this")
        (source / "exclude.log").write_text("Exclude this")
        (source / "exclude.tmp").write_text("Also exclude")

        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            [
                "freeze",
                str(source),
                str(dest),
                "--exclude",
                "*.log",
                "--exclude",
                "*.tmp",
            ],
        )

        assert result.exit_code == 0

        # Extract and check archive contents
        import tarfile

        archives = list(dest.glob("coldstore_*.tar.gz"))
        assert len(archives) == 1

        with tarfile.open(archives[0], "r:gz") as tar:
            names = tar.getnames()
            # Check that keep.txt is included
            assert any("keep.txt" in name for name in names)
            # Check that excluded files are NOT included
            assert not any("exclude.log" in name for name in names)
            assert not any("exclude.tmp" in name for name in names)

    def test_freeze_with_all_metadata(self, tmp_path):
        """Test that milestone, notes, and contacts appear in manifest."""
        runner = CliRunner()

        source = tmp_path / "source"
        source.mkdir()
        (source / "test.txt").write_text("Test")

        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            [
                "freeze",
                str(source),
                str(dest),
                "--milestone",
                "Test Release",
                "--note",
                "First note",
                "--note",
                "Second note",
                "--contact",
                "John Doe <john@example.com>",
            ],
        )

        assert result.exit_code == 0

        # Check manifest contains metadata
        import json

        manifests = list(dest.glob("*.MANIFEST.json"))
        assert len(manifests) == 1

        manifest_data = json.loads(manifests[0].read_text())
        assert manifest_data["event"]["name"] == "Test Release"
        assert "First note" in manifest_data["event"]["notes"]
        assert "Second note" in manifest_data["event"]["notes"]
        assert "John Doe <john@example.com>" in manifest_data["event"]["contacts"]

    def test_freeze_custom_name(self, tmp_path):
        """Test that custom archive name works."""
        runner = CliRunner()

        source = tmp_path / "source"
        source.mkdir()
        (source / "test.txt").write_text("Test")

        dest = tmp_path / "dest"

        result = runner.invoke(
            app, ["freeze", str(source), str(dest), "--name", "my_custom_archive"]
        )

        assert result.exit_code == 0

        # Check that archive has custom name
        archive_path = dest / "my_custom_archive.tar.gz"
        assert archive_path.exists()

    def test_freeze_disabled_features(self, tmp_path):
        """Test that --no-manifest, --no-filelist, --no-sha256 work."""
        runner = CliRunner()

        source = tmp_path / "source"
        source.mkdir()
        (source / "test.txt").write_text("Test")

        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            [
                "freeze",
                str(source),
                str(dest),
                "--no-manifest",
                "--no-filelist",
                "--no-sha256",
            ],
        )

        assert result.exit_code == 0

        # Check that MANIFEST.json is NOT created
        manifests = list(dest.glob("*.MANIFEST.json"))
        assert len(manifests) == 0

        # Check that SHA256 file is NOT created
        sha256_files = list(dest.glob("*.sha256"))
        assert len(sha256_files) == 0

        # Archive should still be created
        archives = list(dest.glob("coldstore_*.tar.gz"))
        assert len(archives) == 1

    def test_freeze_error_nonexistent_source(self, tmp_path):
        """Test error handling for non-existent source."""
        runner = CliRunner()

        source = tmp_path / "nonexistent"
        dest = tmp_path / "dest"

        result = runner.invoke(app, ["freeze", str(source), str(dest)])

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_freeze_error_source_is_file(self, tmp_path):
        """Test error handling when source is a file, not directory."""
        runner = CliRunner()

        source = tmp_path / "file.txt"
        source.write_text("Not a directory")
        dest = tmp_path / "dest"

        result = runner.invoke(app, ["freeze", str(source), str(dest)])

        assert result.exit_code == 1
        assert "not a directory" in result.output

    def test_freeze_error_archive_already_exists(self, tmp_path):
        """Test error handling when archive already exists."""
        runner = CliRunner()

        source = tmp_path / "source"
        source.mkdir()
        (source / "test.txt").write_text("Test")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Create first archive with custom name
        result1 = runner.invoke(
            app, ["freeze", str(source), str(dest), "--name", "duplicate"]
        )
        assert result1.exit_code == 0

        # Try to create second archive with same name
        result2 = runner.invoke(
            app, ["freeze", str(source), str(dest), "--name", "duplicate"]
        )
        assert result2.exit_code == 1
        assert "already exists" in result2.output
