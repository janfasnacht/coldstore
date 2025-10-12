"""Tests for manifest schema and serialization."""


import pytest

from coldstore.core.manifest import (
    ArchiveMetadata,
    ColdstoreManifest,
    EnvironmentMetadata,
    EventMetadata,
    FileEntry,
    FileType,
    GitMetadata,
    MemberCount,
    SourceMetadata,
    SystemMetadata,
    ToolsMetadata,
)


class TestManifestSchema:
    """Test manifest schema validation and structure."""

    def test_minimal_manifest(self):
        """Test creating manifest with minimal required fields."""
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="2025-01-01_00-00-00_abc123",
            source=SourceMetadata(root="/test/path"),
            environment=EnvironmentMetadata(
                system=SystemMetadata(
                    os="Darwin", os_version="23.6.0", hostname="test-host"
                ),
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.11.0"),
            ),
            git=GitMetadata(present=False),
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="a" * 64,
                member_count=MemberCount(files=10, dirs=2),
            ),
        )

        assert manifest.manifest_version == "1.0"
        assert manifest.id == "2025-01-01_00-00-00_abc123"
        assert manifest.source.root == "/test/path"
        assert manifest.git.present is False

    def test_full_manifest_with_event(self):
        """Test manifest with event metadata."""
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="test-id",
            source=SourceMetadata(root="/test"),
            event=EventMetadata(
                type="milestone",
                name="PNAS submission",
                notes=["Final version"],
                contacts=["John Doe <john@example.com>"],
            ),
            environment=EnvironmentMetadata(
                system=SystemMetadata(os="Linux", os_version="5.10", hostname="node1"),
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(
                present=True,
                commit="abc123",
                branch="main",
                tag="v1.0",
                dirty=False,
                remote_origin_url="https://github.com/user/repo.git",
            ),
            archive=ArchiveMetadata(
                filename="archive.tar.gz",
                size_bytes=2048,
                sha256="b" * 64,
                member_count=MemberCount(files=20, dirs=5, symlinks=1),
            ),
        )

        assert manifest.event.type == "milestone"
        assert manifest.event.name == "PNAS submission"
        assert manifest.git.commit == "abc123"
        assert manifest.git.dirty is False

    def test_file_entries(self):
        """Test file entry validation."""
        file_entry = FileEntry(
            path="README.md",
            type=FileType.FILE,
            size=1024,
            mode="0644",
            mtime_utc="2025-01-01T00:00:00Z",
            sha256="c" * 64,
        )

        assert file_entry.path == "README.md"
        assert file_entry.type == FileType.FILE
        assert file_entry.size == 1024
        assert file_entry.sha256 == "c" * 64

    def test_symlink_entry(self):
        """Test symlink file entry."""
        symlink = FileEntry(
            path="link",
            type=FileType.SYMLINK,
            size=0,
            mode="0777",
            mtime_utc="2025-01-01T00:00:00Z",
            link_target="../target",
        )

        assert symlink.type == FileType.SYMLINK
        assert symlink.link_target == "../target"


class TestManifestSerialization:
    """Test YAML and JSON serialization."""

    @pytest.fixture
    def sample_manifest(self):
        """Create a sample manifest for testing."""
        return ColdstoreManifest(
            created_utc="2025-01-01T12:00:00Z",
            id="test-archive-id",
            source=SourceMetadata(root="/home/user/project"),
            event=EventMetadata(type="milestone", name="v1.0 release"),
            environment=EnvironmentMetadata(
                system=SystemMetadata(
                    os="Darwin", os_version="23.6.0", hostname="macbook"
                ),
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.11.9"),
            ),
            git=GitMetadata(
                present=True, commit="abc123def", branch="main", dirty=False
            ),
            archive=ArchiveMetadata(
                filename="project.tar.gz",
                size_bytes=4096,
                sha256="e" * 64,
                member_count=MemberCount(files=15, dirs=3),
            ),
            files=[
                FileEntry(
                    path="file1.txt",
                    type=FileType.FILE,
                    size=100,
                    mode="0644",
                    mtime_utc="2025-01-01T10:00:00Z",
                    sha256="f" * 64,
                )
            ],
        )

    def test_yaml_serialization(self, sample_manifest):
        """Test YAML serialization and deserialization."""
        yaml_str = sample_manifest.to_yaml()

        assert "manifest_version: '1.0'" in yaml_str
        assert "test-archive-id" in yaml_str
        assert "/home/user/project" in yaml_str
        assert "v1.0 release" in yaml_str

        # Test round-trip
        restored = ColdstoreManifest.from_yaml(yaml_str)
        assert restored.id == sample_manifest.id
        assert restored.source.root == sample_manifest.source.root
        assert restored.git.commit == sample_manifest.git.commit

    def test_json_serialization(self, sample_manifest):
        """Test JSON serialization and deserialization."""
        json_str = sample_manifest.to_json()

        assert '"manifest_version": "1.0"' in json_str
        assert '"test-archive-id"' in json_str
        assert '"/home/user/project"' in json_str

        # Test round-trip
        restored = ColdstoreManifest.from_json(json_str)
        assert restored.id == sample_manifest.id
        assert restored.source.root == sample_manifest.source.root
        assert restored.archive.size_bytes == sample_manifest.archive.size_bytes

    def test_exclude_none_in_serialization(self):
        """Test that None values are excluded from serialization."""
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="test",
            source=SourceMetadata(root="/test"),
            environment=EnvironmentMetadata(
                system=SystemMetadata(os="Linux", os_version="5.10", hostname="test"),
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(present=False),  # No git fields set
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="a" * 64,
                member_count=MemberCount(files=1, dirs=1),
            ),
        )

        json_str = manifest.to_json()
        yaml_str = manifest.to_yaml()

        # These fields should not appear since they're None
        assert '"commit":' not in json_str
        assert '"branch":' not in json_str
        assert "commit:" not in yaml_str
        assert "branch:" not in yaml_str


class TestFileListSchema:
    """Test FILELIST.csv.gz schema definitions."""

    def test_filelist_columns(self):
        """Test FILELIST column definitions."""
        from coldstore.core.manifest import FILELIST_COLUMNS

        expected_columns = [
            "relpath",
            "type",
            "size_bytes",
            "mode_octal",
            "uid",
            "gid",
            "mtime_utc",
            "sha256",
            "link_target",
            "is_executable",
            "ext",
        ]

        assert FILELIST_COLUMNS == expected_columns

    def test_filelist_dtypes(self):
        """Test FILELIST data type mappings."""
        from coldstore.core.manifest import FILELIST_DTYPES

        assert FILELIST_DTYPES["relpath"] == str
        assert FILELIST_DTYPES["size_bytes"] == int
        assert FILELIST_DTYPES["is_executable"] == int
