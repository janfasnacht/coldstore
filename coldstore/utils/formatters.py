"""Formatting utilities for coldstore."""

import re
from typing import Optional


def format_size(bytes_: int) -> str:
    """Format bytes as human-readable size.

    Args:
        bytes_: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB", "42.3 MB")

    Examples:
        >>> format_size(0)
        '0 B'
        >>> format_size(1024)
        '1.0 KB'
        >>> format_size(1536)
        '1.5 KB'
        >>> format_size(1073741824)
        '1.0 GB'
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_ < 1024.0:
            if unit == "B":
                return f"{int(bytes_)} {unit}"
            return f"{bytes_:.1f} {unit}"
        bytes_ /= 1024.0
    return f"{bytes_:.1f} PB"


# Backward compatibility alias
get_human_size = format_size


def format_time(seconds: float) -> str:
    """Format time duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2m 15s", "45s", "1h 23m")

    Examples:
        >>> format_time(45)
        '45s'
        >>> format_time(135)
        '2m 15s'
        >>> format_time(3723)
        '1h 2m'
    """
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        if secs > 0:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"


def _get_size_multiplier(unit: str) -> int:
    """Get the multiplier for a size unit."""
    multipliers = {
        '': 1, 'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4,
        'PB': 1024 ** 5,
        'EB': 1024 ** 6,
    }

    if unit in multipliers:
        return multipliers[unit]
    raise ValueError(f"Unknown size unit: {unit}")


def parse_size(size_str: str) -> int:
    """Parse human-readable size string to bytes.

    Args:
        size_str: Size string like '2GB', '500MB', '1.5TB'

    Returns:
        Size in bytes

    Raises:
        ValueError: If size string format is invalid
    """
    if not size_str:
        raise ValueError("Size string cannot be empty")

    # Remove whitespace and convert to uppercase
    size_str = size_str.strip().upper()

    # Extract number and unit using regex
    match = re.match(r'^([0-9]*\.?[0-9]+)\s*([KMGTPE]?B?)$', size_str)
    if not match:
        raise ValueError(
            f"Invalid size format: {size_str}. "
            "Use format like '2GB', '500MB'"
        )

    number_str, unit = match.groups()

    try:
        number = float(number_str)
    except ValueError as e:
        raise ValueError(f"Invalid number in size: {number_str}") from e

    multiplier = _get_size_multiplier(unit)
    return int(number * multiplier)


def generate_readme(
    base_name: str,
    source_name: str,
    source_path: str,
    timestamp: str,
    meta: dict,
    file_tree: str,
    sha256_hash: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    """Generate a comprehensive README with enhanced metadata.

    Args:
        base_name: Base name for the archive
        source_name: Name of the source directory
        source_path: Original path of the source directory
        timestamp: Archive creation timestamp
        meta: Metadata dictionary from get_metadata()
        file_tree: String representation of file tree
        sha256_hash: Optional SHA256 hash of archive
        note: Optional user-provided note

    Returns:
        Formatted README content as string
    """
    file_types_section = ""
    if meta.get("top_file_types"):
        file_types_section = "## File Types\n\n"
        for ext, count in meta["top_file_types"]:
            file_types_section += f"- {ext}: {count} files\n"

    large_files_section = ""
    if meta.get("largest_files"):
        large_files_section = "## Largest Files\n\n"
        for path, size in meta["largest_files"]:
            large_files_section += f"- {path}: {size}\n"

    system_info = meta.get("system_info", {})
    split_info = meta.get("split_archive", {})

    # Build split archive section if applicable
    split_section = ""
    if split_info.get("is_split"):
        split_section = f"""## Split Archive Information
- Archive type: Split archive
- Number of parts: {split_info['num_parts']}
- Total compressed size: {get_human_size(split_info['total_size'])}
- Parts:
"""
        for i, part_name in enumerate(split_info['part_files'], 1):
            split_section += f"  {i}. {part_name}\n"
        split_section += "\n"

    return f"""# Archive: {base_name}

## Source Information
- Source: `{source_name}`
- Archived from: `{source_path}`
- Archive date: {timestamp}
- Created by: {system_info.get('username', 'Unknown')} on \
  {system_info.get('hostname', 'Unknown')} ({system_info.get('os', 'Unknown')})

## Contents Summary
- Files: {meta['file_count']}
- Directories: {meta.get('directory_count', 'N/A')}
- Total size: {meta.get('total_size_human', meta.get('total_size_gb', 'N/A'))}
- Data range: {meta['earliest_date']} to {meta['latest_date']}
{f'- SHA256: `{sha256_hash}`' if sha256_hash else ''}

## Notes
{note or "(No additional notes provided)"}

{split_section}{file_types_section}
{large_files_section}
## Directory Structure (up to 2 levels)

```text
{file_tree}
```

---
Created with coldstore on {meta.get('archive_date', timestamp)}
https://github.com/janfasnacht/coldstore
"""
