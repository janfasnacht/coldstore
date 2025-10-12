"""Strengthened tests for manifest schema and serialization.

This file contains improved validation tests and edge case tests
for the manifest schema that were missing or weak in the original tests.
"""

import pytest

from coldstore.core.manifest import (
    ColdstoreManifest,
    SourceMetadata,
    EnvironmentMetadata,
    SystemMetadata,
    ToolsMetadata,
    GitMetadata,
    ArchiveMetadata,
    MemberCount,
    FileEntry,
    FileType,
    EventMetadata,
)


class TestManifestValidation:
    """Test manifest schema validation comprehensively."""

    def test_manifest_rejects_invalid_sha256(self):
        """Test that archive SHA256 validation works."""
        with pytest.raises(ValueError, match="SHA256 must be 64 hexadecimal"):
            ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="invalid_hash",  # Too short, not hex
                member_count=MemberCount(files=1, dirs=1),
            )

    def test_manifest_normalizes_sha256_case(self):
        """Test that SHA256 is normalized to lowercase."""
        archive = ArchiveMetadata(
            filename="test.tar.gz",
            size_bytes=1024,
            sha256="A" * 64,  # Uppercase
            member_count=MemberCount(files=1, dirs=1),
        )
        assert archive.sha256 == "a" * 64

    def test_file_entry_validates_relative_paths(self):
        """Test that FileEntry rejects absolute paths."""
        # Absolute Unix path
        with pytest.raises(ValueError, match="Path must be relative"):
            FileEntry(
                path="/usr/local/bin/file",
                type=FileType.FILE,
                size=100,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
            )

        # Another absolute path
        with pytest.raises(ValueError, match="Path must be relative"):
            FileEntry(
                path="/var/tmp/test.txt",
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
        # Invalid: contains non-octal digit
        with pytest.raises(ValueError, match="Mode must be valid octal"):
            FileEntry(
                path="test.txt",
                type=FileType.FILE,
                size=100,
                mode="0999",  # 9 is not valid octal
                mtime_utc="2025-01-01T00:00:00Z",
            )

        # Invalid: not numeric
        with pytest.raises(ValueError, match="Mode must be valid octal"):
            FileEntry(
                path="test.txt",
                type=FileType.FILE,
                size=100,
                mode="rwxr-xr-x",  # String notation not allowed
                mtime_utc="2025-01-01T00:00:00Z",
            )

    def test_file_entry_optional_fields(self):
        """Test that optional fields work correctly."""
        # Minimal file entry (no sha256, no link_target)
        entry = FileEntry(
            path="file.txt",
            type=FileType.FILE,
            size=100,
            mode="0644",
            mtime_utc="2025-01-01T00:00:00Z",
        )
        assert entry.sha256 is None
        assert entry.link_target is None

        # Directory with no size
        dir_entry = FileEntry(
            path="directory",
            type=FileType.DIR,
            size=None,
            mode="0755",
            mtime_utc="2025-01-01T00:00:00Z",
        )
        assert dir_entry.size is None


class TestSerializationRoundTrips:
    """Test serialization/deserialization round-trips preserve data."""

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
                    coldstore_version="2.0.0", python_version="3.11.9"
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
                FileEntry(
                    path="src/main.py",
                    type=FileType.FILE,
                    size=4096,
                    mode="0755",
                    mtime_utc="2025-01-01T11:00:00Z",
                    sha256="d" * 64,
                ),
            ],
        )

        # Round-trip through YAML
        yaml_str = manifest.to_yaml()
        restored = ColdstoreManifest.from_yaml(yaml_str)

        # Verify ALL fields preserved
        assert restored.created_utc == manifest.created_utc
        assert restored.id == manifest.id
        assert restored.source.root == manifest.source.root
        assert restored.event.type == manifest.event.type
        assert restored.event.name == manifest.event.name
        assert restored.event.notes == manifest.event.notes
        assert restored.event.contacts == manifest.event.contacts
        assert restored.git.commit == manifest.git.commit
        assert restored.git.tag == manifest.git.tag
        assert restored.archive.size_bytes == manifest.archive.size_bytes
        assert len(restored.files) == len(manifest.files)
        assert restored.files[0].path == manifest.files[0].path
        assert restored.files[0].sha256 == manifest.files[0].sha256

    def test_json_roundtrip_preserves_all_fields(self):
        """Test that JSON round-trip preserves ALL fields exactly."""
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="json-test-id",
            source=SourceMetadata(root="/test/path"),
            environment=EnvironmentMetadata(
                system=SystemMetadata(os="Linux", os_version="5.10", hostname="host"),
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(present=False),
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=999,
                sha256="c" * 64,
                member_count=MemberCount(files=5, dirs=2),
            ),
        )

        # Round-trip through JSON
        json_str = manifest.to_json()
        restored = ColdstoreManifest.from_json(json_str)

        # Verify preservation
        assert restored.created_utc == manifest.created_utc
        assert restored.id == manifest.id
        assert restored.source.root == manifest.source.root
        assert restored.git.present == manifest.git.present
        assert restored.archive.size_bytes == manifest.archive.size_bytes

    def test_exclude_none_works_consistently(self):
        """Test that None exclusion works for both YAML and JSON."""
        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="test",
            source=SourceMetadata(root="/test"),
            environment=EnvironmentMetadata(
                system=SystemMetadata(os="Linux", os_version="5.10", hostname="test"),
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(present=False),  # All optional fields are None
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="a" * 64,
                member_count=MemberCount(files=1, dirs=1),
            ),
        )

        yaml_str = manifest.to_yaml()
        json_str = manifest.to_json()

        # None fields should not appear in either format
        for field in ["commit", "branch", "tag", "dirty", "remote_origin_url"]:
            assert f"{field}:" not in yaml_str
            assert f'"{field}":' not in json_str


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
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(present=False),
            archive=ArchiveMetadata(
                filename="empty.tar.gz",
                size_bytes=100,
                sha256="e" * 64,
                member_count=MemberCount(files=0, dirs=0),
            ),
            files=[],  # Empty list
        )

        # Should serialize and deserialize correctly
        yaml_str = manifest.to_yaml()
        restored = ColdstoreManifest.from_yaml(yaml_str)
        assert len(restored.files) == 0

    def test_large_file_list(self):
        """Test manifest with many files (performance check)."""
        # Create 1000 file entries
        files = [
            FileEntry(
                path=f"file_{i:04d}.txt",
                type=FileType.FILE,
                size=100 * i,
                mode="0644",
                mtime_utc="2025-01-01T00:00:00Z",
                sha256="a" * 64,
            )
            for i in range(1000)
        ]

        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="large-manifest",
            source=SourceMetadata(root="/test"),
            environment=EnvironmentMetadata(
                system=SystemMetadata(os="Linux", os_version="5.10", hostname="test"),
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(present=False),
            archive=ArchiveMetadata(
                filename="large.tar.gz",
                size_bytes=100000,
                sha256="f" * 64,
                member_count=MemberCount(files=1000, dirs=0),
            ),
            files=files,
        )

        # Should serialize without error
        yaml_str = manifest.to_yaml()
        json_str = manifest.to_json()

        # Should deserialize correctly
        restored_yaml = ColdstoreManifest.from_yaml(yaml_str)
        restored_json = ColdstoreManifest.from_json(json_str)

        assert len(restored_yaml.files) == 1000
        assert len(restored_json.files) == 1000

    def test_event_metadata_multiple_notes_and_contacts(self):
        """Test EventMetadata with multiple notes and contacts."""
        event = EventMetadata(
            type="milestone",
            name="Major Release",
            notes=[
                "First line of notes",
                "Second line with special chars: @#$%",
                "Third line with unicode: émoji 🎉",
            ],
            contacts=[
                "user1@example.com",
                "user2@example.com",
                "John Doe <john@example.com>",
            ],
        )

        manifest = ColdstoreManifest(
            created_utc="2025-01-01T00:00:00Z",
            id="test",
            source=SourceMetadata(root="/test"),
            event=event,
            environment=EnvironmentMetadata(
                system=SystemMetadata(os="Linux", os_version="5.10", hostname="test"),
                tools=ToolsMetadata(coldstore_version="2.0.0", python_version="3.9.0"),
            ),
            git=GitMetadata(present=False),
            archive=ArchiveMetadata(
                filename="test.tar.gz",
                size_bytes=1024,
                sha256="a" * 64,
                member_count=MemberCount(files=1, dirs=1),
            ),
        )

        # Round-trip
        yaml_str = manifest.to_yaml()
        restored = ColdstoreManifest.from_yaml(yaml_str)

        assert len(restored.event.notes) == 3
        assert len(restored.event.contacts) == 3
        assert "émoji 🎉" in restored.event.notes[2]


class TestFILELISTSchemaValidation:
    """Test FILELIST.csv.gz schema definitions more thoroughly."""

    def test_filelist_columns_order_matters(self):
        """Test that FILELIST columns are in exact expected order."""
        from coldstore.core.manifest import FILELIST_COLUMNS

        # Order matters for CSV
        assert FILELIST_COLUMNS[0] == "relpath"
        assert FILELIST_COLUMNS[1] == "type"
        assert FILELIST_COLUMNS[2] == "size_bytes"
        assert FILELIST_COLUMNS[7] == "sha256"
        assert FILELIST_COLUMNS[-1] == "ext"

    def test_filelist_dtypes_complete(self):
        """Test that all FILELIST columns have dtype definitions."""
        from coldstore.core.manifest import FILELIST_COLUMNS, FILELIST_DTYPES

        # Every column should have a dtype
        for column in FILELIST_COLUMNS:
            assert column in FILELIST_DTYPES, f"Missing dtype for {column}"

    def test_filelist_dtypes_correct_types(self):
        """Test that FILELIST dtypes are correct Python types."""
        from coldstore.core.manifest import FILELIST_DTYPES

        # Check specific types
        assert FILELIST_DTYPES["relpath"] == str
        assert FILELIST_DTYPES["type"] == str
        assert FILELIST_DTYPES["size_bytes"] == int
        assert FILELIST_DTYPES["uid"] == int
        assert FILELIST_DTYPES["gid"] == int
        assert FILELIST_DTYPES["is_executable"] == int  # Boolean as int (0/1)
