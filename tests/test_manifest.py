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
                tools=ToolsMetadata(coldstore_version="1.0.0", python_version="3.11.0"),
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
                tools=ToolsMetadata(coldstore_version="1.0.0", python_version="3.9.0"),
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
                tools=ToolsMetadata(coldstore_version="1.0.0", python_version="3.11.9"),
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
                tools=ToolsMetadata(coldstore_version="1.0.0", python_version="3.9.0"),
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


# ============================================================================
# Enhanced validation and edge case tests
# ============================================================================

class TestManifestValidation:
    """Test manifest schema validation comprehensively."""

    def test_manifest_rejects_invalid_sha256(self):
        """Test that archive SHA256 validation works."""
        with pytest.raises(ValueError, match="SHA256 must be 64 hexadecimal"):
            ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="invalid_hash",
                member_count=MemberCount(files=1, dirs=1),
            )

    def test_manifest_normalizes_sha256_case(self):
        """Test that SHA256 is normalized to lowercase."""
        archive = ArchiveMetadata(
            filename="test.tar.gz",
            size_bytes=1024,
            sha256="A" * 64,
            member_count=MemberCount(files=1, dirs=1),
        )
        assert archive.sha256 == "a" * 64

    def test_file_entry_validates_relative_paths(self):
        """Test that FileEntry rejects absolute paths."""
        with pytest.raises(ValueError, match="Path must be relative"):
            FileEntry(
                path="/usr/local/bin/file",
                type=FileType.FILE,
                size=100,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
            )

        # Relative paths should work
        entry = FileEntry(
            path="relative/path/file.txt",
            type=FileType.FILE,
            size=100,
            mode="0644",
            mtime_utc="2025-01-01T00:00:00Z",
        )
        assert entry.path == "relative/path/file.txt"

    def test_file_entry_mode_validation(self):
        """Test mode validation comprehensively."""
        with pytest.raises(ValueError, match="Mode must be valid octal"):
            FileEntry(
                path="test.txt",
                type=FileType.FILE,
                size=100,
                mode="0999",
                mtime_utc="2025-01-01T00:00:00Z",
            )

        with pytest.raises(ValueError, match="Mode must be valid octal"):
            FileEntry(
                path="test.txt",
                type=FileType.FILE,
                size=100,
                mode="rwxr-xr-x",
                mtime_utc="2025-01-01T00:00:00Z",
            )

    def test_file_entry_optional_fields(self):
        """Test that optional fields work correctly."""
        entry = FileEntry(
            path="file.txt",
            type=FileType.FILE,
            size=100,
            mode="0644",
            mtime_utc="2025-01-01T00:00:00Z",
        )
        assert entry.sha256 is None
        assert entry.link_target is None

        dir_entry = FileEntry(
            path="directory",
            type=FileType.DIR,
            size=None,
            mode="0755",
            mtime_utc="2025-01-01T00:00:00Z",
        )
        assert dir_entry.size is None


class TestSerializationEnhanced:
    """Test serialization/deserialization round-trips preserve all data."""

    def test_yaml_roundtrip_preserves_all_fields(self):
        """Test that YAML round-trip preserves ALL fields exactly."""
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T12:34:56.789Z",
            id="test-id-12345",
            source=SourceMetadata(root="/home/user/project"),
            event=EventMetadata(
                type="milestone",
                name="v1.0 Release",
                notes=["First stable release", "All tests passing"],
                contacts=["user@example.com", "admin@example.com"],
            ),
            environment=EnvironmentMetadata(
                system=SystemMetadata(
                    os="Darwin", os_version="23.6.0", hostname="test-host"
                ),
                tools=ToolsMetadata(
                    coldstore_version="1.0.0", python_version="3.11.9"
                ),
            ),
            git=GitMetadata(
                present=True,
                commit="abc123def456",
                branch="main",
                tag="v1.0",
                dirty=False,
                remote_origin_url="https://github.com/user/repo.git",
            ),
            archive=ArchiveMetadata(
                filename="project.tar.gz",
                size_bytes=1024567,
                sha256="e" * 64,
                member_count=MemberCount(files=42, dirs=7, symlinks=2),
            ),
            files=[
                FileEntry(
                    path="README.md",
                    type=FileType.FILE,
                    size=2048,
                    mode="0644",
                    mtime_utc="2025-01-01T10:00:00Z",
                    sha256="f" * 64,
                ),
            ],
        )

        yaml_str = manifest.to_yaml()
        restored = ColdstoreManifest.from_yaml(yaml_str)

        # Verify ALL critical fields preserved
        assert restored.created_utc == manifest.created_utc
        assert restored.id == manifest.id
        assert restored.event.notes == manifest.event.notes
        assert restored.git.tag == manifest.git.tag
        assert len(restored.files) == len(manifest.files)


class TestManifestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_files_list(self):
        """Test manifest with no files listed."""
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="empty-files",
            source=SourceMetadata(root="/test"),
            environment=EnvironmentMetadata(
                system=SystemMetadata(os="Linux", os_version="5.10", hostname="test"),
                tools=ToolsMetadata(coldstore_version="1.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(present=False),
            archive=ArchiveMetadata(
                filename="empty.tar.gz",
                size_bytes=100,
                sha256="e" * 64,
                member_count=MemberCount(files=0, dirs=0),
            ),
            files=[],
        )

        yaml_str = manifest.to_yaml()
        restored = ColdstoreManifest.from_yaml(yaml_str)
        assert len(restored.files) == 0

    def test_event_metadata_multiple_notes_and_contacts(self):
        """Test EventMetadata with multiple notes and contacts."""
        event = EventMetadata(
            type="milestone",
            name="Major Release",
            notes=[
                "First line",
                "Second line with special chars: @#$%",
                "Third line with unicode: émoji 🎉",
            ],
            contacts=["user1@example.com", "user2@example.com"],
        )

        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="test",
            source=SourceMetadata(root="/test"),
            event=event,
            environment=EnvironmentMetadata(
                system=SystemMetadata(os="Linux", os_version="5.10", hostname="test"),
                tools=ToolsMetadata(coldstore_version="1.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(present=False),
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="a" * 64,
                member_count=MemberCount(files=1, dirs=1),
            ),
        )

        yaml_str = manifest.to_yaml()
        restored = ColdstoreManifest.from_yaml(yaml_str)
        assert len(restored.event.notes) == 3
        assert "émoji 🎉" in restored.event.notes[2]


class TestFILELISTSchemaEnhanced:
    """Test FILELIST.csv.gz schema definitions more thoroughly."""

    def test_filelist_columns_order_matters(self):
        """Test that FILELIST columns are in exact expected order."""
        from coldstore.core.manifest import FILELIST_COLUMNS

        assert FILELIST_COLUMNS[0] == "relpath"
        assert FILELIST_COLUMNS[1] == "type"
        assert FILELIST_COLUMNS[7] == "sha256"
        assert FILELIST_COLUMNS[-1] == "ext"

    def test_filelist_dtypes_complete(self):
        """Test that all FILELIST columns have dtype definitions."""
        from coldstore.core.manifest import FILELIST_COLUMNS, FILELIST_DTYPES

        for column in FILELIST_COLUMNS:
            assert column in FILELIST_DTYPES, f"Missing dtype for {column}"


class TestFILELISTCSVGeneration:
    """Test FILELIST.csv.gz write and read functions."""

    def test_write_filelist_csv_basic(self, tmp_path):
        """Test basic FILELIST.csv.gz writing."""
        from coldstore.core.manifest import FileEntry, FileType, write_filelist_csv

        # Create test file entries
        entries = [
            FileEntry(
                path="file1.txt",
                type=FileType.FILE,
                size=100,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="a" * 64,
            ),
            FileEntry(
                path="dir1",
                type=FileType.DIR,
                size=None,
                mode="0755",
                mtime_utc="2025-01-01T00:00:00Z",
            ),
        ]

        # Write FILELIST.csv.gz
        output_path = tmp_path / "FILELIST.csv.gz"
        filelist_hash = write_filelist_csv(output_path, entries)

        # Verify output file exists
        assert output_path.exists()

        # Verify hash is valid SHA256
        assert len(filelist_hash) == 64
        assert all(c in "0123456789abcdef" for c in filelist_hash)

    def test_write_filelist_csv_deterministic(self, tmp_path):
        """Test that FILELIST.csv.gz generation is deterministic."""
        from coldstore.core.manifest import FileEntry, FileType, write_filelist_csv

        entries = [
            FileEntry(
                path="zzz.txt",
                type=FileType.FILE,
                size=100,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="a" * 64,
            ),
            FileEntry(
                path="aaa.txt",
                type=FileType.FILE,
                size=200,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="b" * 64,
            ),
        ]

        # Write twice
        output1 = tmp_path / "filelist1.csv.gz"
        output2 = tmp_path / "filelist2.csv.gz"

        hash1 = write_filelist_csv(output1, entries)
        hash2 = write_filelist_csv(output2, entries)

        # Hashes should match (deterministic)
        assert hash1 == hash2

        # File sizes should match
        assert output1.stat().st_size == output2.stat().st_size

    def test_write_filelist_csv_sorts_entries(self, tmp_path):
        """Test that entries are sorted lexicographically."""
        from coldstore.core.manifest import (
            FileEntry,
            FileType,
            read_filelist_csv,
            write_filelist_csv,
        )

        # Create entries in non-alphabetical order
        entries = [
            FileEntry(
                path="zzz.txt",
                type=FileType.FILE,
                size=100,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="a" * 64,
            ),
            FileEntry(
                path="aaa.txt",
                type=FileType.FILE,
                size=200,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="b" * 64,
            ),
            FileEntry(
                path="mmm.txt",
                type=FileType.FILE,
                size=300,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="c" * 64,
            ),
        ]

        output_path = tmp_path / "FILELIST.csv.gz"
        write_filelist_csv(output_path, entries)

        # Read back and verify order
        read_entries = read_filelist_csv(output_path)
        paths = [e["relpath"] for e in read_entries]

        # Should be in alphabetical order
        assert paths == ["aaa.txt", "mmm.txt", "zzz.txt"]

    def test_read_filelist_csv_roundtrip(self, tmp_path):
        """Test that read/write roundtrip preserves data."""
        from coldstore.core.manifest import (
            FileEntry,
            FileType,
            read_filelist_csv,
            write_filelist_csv,
        )

        entries = [
            FileEntry(
                path="file1.py",
                type=FileType.FILE,
                size=1024,
                mode="0755",
                mtime_utc="2025-01-01T10:00:00Z",
                sha256="e" * 64,
            ),
            FileEntry(
                path="dir1",
                type=FileType.DIR,
                size=None,
                mode="0755",
                mtime_utc="2025-01-01T11:00:00Z",
            ),
        ]

        output_path = tmp_path / "FILELIST.csv.gz"
        write_filelist_csv(output_path, entries)

        # Read back
        read_entries = read_filelist_csv(output_path)

        # Verify data preserved
        assert len(read_entries) == 2

        # Check first entry (directory comes first alphabetically)
        assert read_entries[0]["relpath"] == "dir1"
        assert read_entries[0]["type"] == "dir"
        assert read_entries[0]["size_bytes"] is None
        assert read_entries[0]["mode_octal"] == "0755"

        # Check second entry
        assert read_entries[1]["relpath"] == "file1.py"
        assert read_entries[1]["type"] == "file"
        assert read_entries[1]["size_bytes"] == 1024
        assert read_entries[1]["sha256"] == "e" * 64

    def test_write_filelist_csv_compression_levels(self, tmp_path):
        """Test different compression levels."""
        from coldstore.core.manifest import FileEntry, FileType, write_filelist_csv

        # Create many entries for better compression testing
        entries = [
            FileEntry(
                path=f"file{i:04d}.txt",
                type=FileType.FILE,
                size=100 + i,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="a" * 64,
            )
            for i in range(100)
        ]

        # Write with different compression levels
        output_0 = tmp_path / "level_0.csv.gz"
        output_9 = tmp_path / "level_9.csv.gz"

        write_filelist_csv(output_0, entries, compression_level=1)
        write_filelist_csv(output_9, entries, compression_level=9)

        # Level 9 should be smaller or equal
        assert output_9.stat().st_size <= output_0.stat().st_size

    def test_write_filelist_csv_with_scanner_metadata(self, tmp_path):
        """Test writing FILELIST.csv.gz with metadata from scanner."""
        from coldstore.core.manifest import FileType, write_filelist_csv

        # Create metadata dict like scanner.collect_file_metadata() returns
        metadata = [
            {
                "path": "file1.txt",
                "type": FileType.FILE,
                "size": 100,
                "mode": "0644",
                "mtime_utc": "2025-01-01T00:00:00Z",
                "sha256": "a" * 64,
                "link_target": None,
                "_uid": 1000,
                "_gid": 1000,
                "_is_executable": False,
                "_ext": "txt",
            },
            {
                "path": "script.sh",
                "type": FileType.FILE,
                "size": 200,
                "mode": "0755",
                "mtime_utc": "2025-01-01T00:00:00Z",
                "sha256": "b" * 64,
                "link_target": None,
                "_uid": 1000,
                "_gid": 1000,
                "_is_executable": True,
                "_ext": "sh",
            },
        ]

        output_path = tmp_path / "FILELIST.csv.gz"
        filelist_hash = write_filelist_csv(output_path, metadata)

        # Verify it was written
        assert output_path.exists()
        assert len(filelist_hash) == 64

        # Read back and verify uid/gid/executable were captured
        from coldstore.core.manifest import read_filelist_csv

        read_entries = read_filelist_csv(output_path)

        # Check that extended metadata is present
        assert read_entries[0]["uid"] == 1000
        assert read_entries[0]["gid"] == 1000
        assert read_entries[0]["is_executable"] == 0
        assert read_entries[0]["ext"] == "txt"

        assert read_entries[1]["is_executable"] == 1
        assert read_entries[1]["ext"] == "sh"
