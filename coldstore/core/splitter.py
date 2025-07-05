"""Archive splitting functionality for coldstore."""

import fnmatch
import tarfile
from pathlib import Path
from typing import Optional

from ..utils.formatters import get_human_size, parse_size


def collect_files_to_archive(
    source_path: Path, exclude_patterns: Optional[list[str]] = None
) -> list[tuple[Path, str]]:
    """Collect all files to be archived with their archive names."""
    files_to_archive = []

    def should_exclude(path: Path) -> bool:
        if not exclude_patterns:
            return False
        rel_path = str(path.relative_to(source_path))
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

    for item in source_path.rglob("*"):
        if item.is_file() and not should_exclude(item):
            # Calculate archive name (relative path from source)
            arc_name = str(item.relative_to(source_path.parent))
            files_to_archive.append((item, arc_name))

    return files_to_archive


def create_single_archive(
    files: list[tuple[Path, str]], archive_path: Path, compress_level: int
) -> None:
    """Create a single tar.gz archive from file list."""
    with tarfile.open(archive_path, "w:gz", compresslevel=compress_level) as tar:
        for file_path, arc_name in files:
            tar.add(file_path, arcname=arc_name)


def create_split_archives(
    source_path: Path,
    source_name: str,
    base_archive_path: Path,
    compress_level: int,
    exclude_patterns: Optional[list[str]],
    split_size: str,
) -> list[Path]:
    """Create multiple archives split by size.

    Args:
        source_path: Path to source directory
        source_name: Name of source directory (unused for splitting)
        base_archive_path: Base path for archive parts
        compress_level: Compression level (1-9)
        exclude_patterns: Patterns to exclude from archive
        split_size: Human-readable size string (e.g., "2GB")

    Returns:
        List of created archive part paths
    """
    max_size_bytes = parse_size(split_size)
    print(f"📦 Creating split archives (max size: {get_human_size(max_size_bytes)})")

    # Collect all files to archive
    files_to_archive = collect_files_to_archive(source_path, exclude_patterns)

    if not files_to_archive:
        print("⚠️  No files to archive")
        return []

    # Sort files by size (largest first) for better packing
    files_to_archive.sort(key=lambda x: x[0].stat().st_size, reverse=True)

    archive_parts = []
    current_part = []
    current_size = 0
    part_num = 1

    print(f"📊 Processing {len(files_to_archive)} files for splitting...")

    for file_path, arc_name in files_to_archive:
        file_size = file_path.stat().st_size

        # Estimate compressed size (rough approximation: 70% of original)
        estimated_compressed = int(file_size * 0.7)

        # If adding this file would exceed the limit, create current archive
        if current_part and (current_size + estimated_compressed) > max_size_bytes:
            # Create archive for current part
            part_path = base_archive_path.with_suffix(f".part{part_num:03d}.tar.gz")
            print(f"  Creating part {part_num}: {part_path.name}")
            create_single_archive(current_part, part_path, compress_level)
            archive_parts.append(part_path)

            # Start new part
            current_part = []
            current_size = 0
            part_num += 1

        current_part.append((file_path, arc_name))
        current_size += estimated_compressed

    # Create final part if there are remaining files
    if current_part:
        if part_num == 1:
            # Only one part, use original name
            part_path = base_archive_path
        else:
            part_path = base_archive_path.with_suffix(f".part{part_num:03d}.tar.gz")
        print(f"  Creating part {part_num}: {part_path.name}")
        create_single_archive(current_part, part_path, compress_level)
        archive_parts.append(part_path)

    print(f"✅ Created {len(archive_parts)} archive parts")
    return archive_parts
