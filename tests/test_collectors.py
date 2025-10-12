"""Tests for metadata collectors."""

import subprocess
import sys

from coldstore.core.collectors import (
    EnvironmentMetadataCollector,
    GitMetadataCollector,
    SystemMetadataCollector,
    collect_environment_metadata,
    collect_git_metadata,
    collect_system_metadata,
)
from coldstore.core.manifest import (
    ArchiveMetadata,
    ColdstoreManifest,
    MemberCount,
    SourceMetadata,
)


class TestGitMetadataCollector:
    """Test git metadata collection."""

    def test_git_not_available(self, tmp_path, monkeypatch):
        """Test when git command is not available."""
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(subprocess, "run", mock_run)

        collector = GitMetadataCollector(tmp_path)
        metadata = collector.collect()

        assert metadata.present is False
        assert metadata.commit is None
        assert metadata.branch is None

    def test_not_a_git_repo(self, tmp_path):
        """Test when path is not a git repository."""
        collector = GitMetadataCollector(tmp_path)
        metadata = collector.collect()

        assert metadata.present is False

    def test_git_repo_basic(self, tmp_path):
        """Test collecting metadata from a basic git repository."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)  # noqa: E501
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        collector = GitMetadataCollector(tmp_path)
        metadata = collector.collect()

        assert metadata.present is True
        assert metadata.commit is not None
        assert len(metadata.commit) == 40  # Full SHA1 hash
        assert (
            metadata.branch == "main" or metadata.branch == "master"
        )  # Depends on git config
        assert metadata.dirty is False  # Clean working tree

    def test_git_repo_dirty(self, tmp_path):
        """Test detecting dirty working tree."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)  # noqa: E501
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Make working tree dirty
        (tmp_path / "test.txt").write_text("modified")

        collector = GitMetadataCollector(tmp_path)
        metadata = collector.collect()

        assert metadata.present is True
        assert metadata.dirty is True

    def test_git_repo_with_tag(self, tmp_path):
        """Test collecting tag information."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)  # noqa: E501
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create tag
        subprocess.run(
            ["git", "tag", "v1.0.0"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        collector = GitMetadataCollector(tmp_path)
        metadata = collector.collect()

        assert metadata.present is True
        assert metadata.tag == "v1.0.0"

    def test_git_repo_with_remote(self, tmp_path):
        """Test collecting remote origin URL."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Add remote origin
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)  # noqa: E501
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        collector = GitMetadataCollector(tmp_path)
        metadata = collector.collect()

        assert metadata.present is True
        assert metadata.remote_origin_url == "https://github.com/user/repo.git"

    def test_convenience_function(self, tmp_path):
        """Test convenience function for collecting git metadata."""
        metadata = collect_git_metadata(tmp_path)
        assert metadata.present is False  # tmp_path is not a git repo


class TestSystemMetadataCollector:
    """Test system metadata collection."""

    def test_collect_system_metadata(self):
        """Test collecting system metadata."""
        collector = SystemMetadataCollector()
        metadata = collector.collect()

        assert metadata.os in ["Darwin", "Linux", "Windows", "Unknown"]
        assert metadata.os_version is not None
        assert len(metadata.os_version) > 0
        assert metadata.hostname is not None
        assert len(metadata.hostname) > 0

    def test_system_metadata_fields_not_empty(self):
        """Test that all system metadata fields are populated."""
        collector = SystemMetadataCollector()
        metadata = collector.collect()

        assert metadata.os != ""
        assert metadata.os_version != ""
        assert metadata.hostname != ""

    def test_convenience_function(self):
        """Test convenience function for collecting system metadata."""
        metadata = collect_system_metadata()
        assert metadata.os is not None


class TestEnvironmentMetadataCollector:
    """Test environment metadata collection."""

    def test_collect_environment_metadata(self):
        """Test collecting environment metadata."""
        collector = EnvironmentMetadataCollector()
        metadata = collector.collect()

        # Verify system metadata
        assert metadata.system.os is not None
        assert metadata.system.os_version is not None
        assert metadata.system.hostname is not None

        # Verify tools metadata
        assert metadata.tools.python_version is not None
        assert metadata.tools.coldstore_version is not None

    def test_python_version_format(self):
        """Test that Python version is in expected format."""
        collector = EnvironmentMetadataCollector()
        metadata = collector.collect()

        python_version = metadata.tools.python_version
        parts = python_version.split(".")
        assert len(parts) == 3  # Major.Minor.Micro
        assert all(part.isdigit() for part in parts)

        # Verify matches actual Python version
        expected = (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )
        assert python_version == expected

    def test_coldstore_version_present(self):
        """Test that coldstore version is detected."""
        collector = EnvironmentMetadataCollector()
        metadata = collector.collect()

        # Should either be a version string or "unknown"
        assert metadata.tools.coldstore_version is not None
        assert len(metadata.tools.coldstore_version) > 0

    def test_custom_system_collector(self):
        """Test using custom system collector."""
        system_collector = SystemMetadataCollector()
        env_collector = EnvironmentMetadataCollector(system_collector=system_collector)

        metadata = env_collector.collect()
        assert metadata.system.os is not None

    def test_convenience_function(self):
        """Test convenience function for collecting environment metadata."""
        metadata = collect_environment_metadata()
        assert metadata.system is not None
        assert metadata.tools is not None


class TestIntegrationWithManifest:
    """Test integration of collectors with manifest creation."""

    def test_create_manifest_with_collected_metadata(self, tmp_path):
        """Test creating a complete manifest with collected metadata."""
        # Initialize git repo for testing
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)  # noqa: E501
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Collect metadata
        git_metadata = collect_git_metadata(tmp_path)
        env_metadata = collect_environment_metadata()

        # Create manifest
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="test-manifest",
            source=SourceMetadata(root=str(tmp_path)),
            environment=env_metadata,
            git=git_metadata,
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="a" * 64,
                member_count=MemberCount(files=1, dirs=0),
            ),
        )

        # Verify manifest is valid
        assert manifest.git.present is True
        assert manifest.git.commit is not None
        assert manifest.environment.system.os is not None
        assert manifest.environment.tools.python_version is not None

        # Test serialization
        yaml_str = manifest.to_yaml()
        assert "git:" in yaml_str
        assert "commit:" in yaml_str
        assert "python_version:" in yaml_str

    def test_manifest_with_non_git_repo(self, tmp_path):
        """Test creating manifest for non-git repository."""
        # Collect metadata from non-git directory
        git_metadata = collect_git_metadata(tmp_path)
        env_metadata = collect_environment_metadata()

        # Create manifest
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="test-no-git",
            source=SourceMetadata(root=str(tmp_path)),
            environment=env_metadata,
            git=git_metadata,
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="b" * 64,
                member_count=MemberCount(files=0, dirs=0),
            ),
        )

        # Verify git is marked as not present
        assert manifest.git.present is False
        assert manifest.git.commit is None

        # Other metadata should still be present
        assert manifest.environment.system.os is not None


class TestErrorHandling:
    """Test error handling in metadata collectors."""

    def test_git_timeout_handling(self, tmp_path, monkeypatch):
        """Test that git command timeouts are handled gracefully."""
        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired("git", timeout=5)

        monkeypatch.setattr(subprocess, "run", mock_run)

        collector = GitMetadataCollector(tmp_path)
        metadata = collector.collect()

        # Should return present=False instead of raising exception
        assert metadata.present is False

    def test_system_metadata_exception_handling(self, monkeypatch):
        """Test that system metadata collection handles exceptions."""
        def mock_system():
            raise OSError("Platform error")

        import platform
        monkeypatch.setattr(platform, "system", mock_system)

        collector = SystemMetadataCollector()
        metadata = collector.collect()

        # Should return fallback values
        assert metadata.os == "Unknown"
        assert metadata.os_version == "Unknown"
        assert metadata.hostname == "Unknown"
