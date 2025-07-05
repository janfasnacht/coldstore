"""File operation utilities for archive_project."""

import subprocess
from pathlib import Path
from typing import Optional


def get_file_tree(source_path: Path, depth: int = 2) -> str:
    """Get directory tree representation using tree command or fallback.
    
    Args:
        source_path: Path to generate tree for
        depth: Maximum depth to display
        
    Returns:
        String representation of directory tree
    """
    try:
        result = subprocess.run(
            ["tree", f"-L{depth}", "--noreport", str(source_path)],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        # Use fallback implementation
        return file_tree_fallback(source_path, depth)


def file_tree_fallback(dir_path: Path, max_depth: int = 2, prefix: str = "") -> str:
    """Generate a file tree structure similar to the 'tree' command without external dependencies.
    
    Args:
        dir_path: Path to directory
        max_depth: Maximum depth to traverse
        prefix: String prefix for current line (used recursively)
        
    Returns:
        String representation of the file tree
    """
    if max_depth < 0:
        return ""

    output = [f"{prefix}{dir_path.name}"]

    try:
        items = sorted(
            list(dir_path.iterdir()), 
            key=lambda p: (p.is_file(), p.name.lower())
        )
    except PermissionError:
        return f"{prefix}{dir_path.name} [Permission Denied]"

    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        item_prefix = prefix + ("└── " if is_last else "├── ")
        next_prefix = prefix + ("    " if is_last else "│   ")

        if item.is_dir():
            if max_depth > 0:
                subtree = file_tree_fallback(item, max_depth - 1, next_prefix)
                output.append(f"{item_prefix}{item.name}")
                if max_depth > 1:  # Only add subtree if we're going deeper
                    for line in subtree.split('\n')[1:]:  # Skip the root line
                        output.append(line)
            else:
                output.append(f"{item_prefix}{item.name}")
        else:
            output.append(f"{item_prefix}{item.name}")

    return "\n".join(output)