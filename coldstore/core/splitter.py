"""Archive splitting functionality for coldstore."""

import fnmatch
import tarfile
from pathlib import Path
from typing import Optional

from ..utils.formatters import get_human_size, parse_size


def estimate_compression_ratio(
    file_path: Path, file_size: int, compress_level: int
) -> float:
    """Estimate compression ratio based on file type and characteristics.

    Args:
        file_path: Path to the file
        file_size: Size of the file in bytes
        compress_level: Compression level (1-9)

    Returns:
        Estimated compression ratio (0.0 to 1.0, where 0.1 = 10% of original size)
    """
    suffix = file_path.suffix.lower()

    # Base compression estimates by file type
    compression_estimates = {
        # Already compressed formats (minimal additional compression)
        '.jpg': 0.95, '.jpeg': 0.95, '.png': 0.90, '.gif': 0.95,
        '.mp4': 0.98, '.avi': 0.98, '.mov': 0.98, '.mkv': 0.98,
        '.mp3': 0.95, '.flac': 0.98, '.wav': 0.45,
        '.zip': 0.95, '.7z': 0.95, '.rar': 0.95, '.gz': 0.95,
        '.pdf': 0.85,

        # Binary formats (moderate compression)
        '.exe': 0.65, '.dll': 0.65, '.so': 0.65,
        '.pyc': 0.60, '.class': 0.60,
        '.pickle': 0.50, '.gpickle': 0.40,  # pickled data often compresses well
        '.db': 0.60, '.sqlite': 0.60,

        # Text-based formats (good compression)
        '.txt': 0.35, '.log': 0.25,  # Logs often have repetitive content
        '.csv': 0.40, '.tsv': 0.40,
        '.json': 0.35, '.xml': 0.30, '.html': 0.30,
        '.py': 0.45, '.js': 0.45, '.css': 0.40,
        '.c': 0.45, '.cpp': 0.45, '.h': 0.45,
        '.java': 0.45, '.kt': 0.45,
        '.md': 0.50, '.rst': 0.50,
        '.yaml': 0.45, '.yml': 0.45,
        '.ini': 0.50, '.conf': 0.45,
        '.do': 0.45,  # Stata do files
        '.r': 0.45,   # R scripts
    }

    # Get base estimate
    base_ratio = compression_estimates.get(suffix, 0.65)  # Default: 65%

    # Adjust for compression level (higher level = better compression)
    # Level 1: +10% size, Level 9: -15% size relative to level 6
    level_adjustment = {
        1: 1.10, 2: 1.08, 3: 1.05, 4: 1.02, 5: 1.0,
        6: 1.0,  # baseline
        7: 0.95, 8: 0.90, 9: 0.85
    }

    adjusted_ratio = base_ratio * level_adjustment.get(compress_level, 1.0)

    # For very large files, assume slightly better compression due to more patterns
    if file_size > 100 * 1024 * 1024:  # > 100MB
        adjusted_ratio *= 0.9
    elif file_size > 1024 * 1024 * 1024:  # > 1GB
        adjusted_ratio *= 0.8

    # Ensure ratio stays within reasonable bounds
    return max(0.1, min(0.98, adjusted_ratio))


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

        # Estimate compressed size based on file type and characteristics
        compression_ratio = estimate_compression_ratio(
            file_path, file_size, compress_level
        )
        estimated_compressed = int(file_size * compression_ratio)

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
