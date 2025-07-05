"""Formatting utilities for archive_project."""

from typing import Optional


def get_human_size(size_bytes: int) -> str:
    """Convert byte size to human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., "1.23 GB")
    """
    if size_bytes == 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {units[i]}"


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

{file_types_section}
{large_files_section}
## Directory Structure (up to 2 levels)

```text
{file_tree}
```

---
Created with coldstore on {meta.get('archive_date', timestamp)}
https://github.com/janfasnacht/coldstore
"""
