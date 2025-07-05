"""Metadata collection functionality for archive_project."""

import datetime
import getpass
import os
import platform
from pathlib import Path
from typing import Any, Optional

from ..utils.formatters import get_human_size


def get_metadata(source_path: Path) -> dict[str, Any]:
    """Enhanced metadata collection with additional useful information.

    Args:
        source_path: Path to the source directory to analyze

    Returns:
        Dictionary containing directory metadata including file counts,
        sizes, dates, etc.
    """
    file_count = 0
    dir_count = 0
    total_size = 0
    earliest: Optional[datetime.datetime] = None
    latest: Optional[datetime.datetime] = None
    file_types: dict[str, int] = {}
    largest_files: list[tuple[Path, int]] = []

    for root, dirs, files in os.walk(source_path):
        dir_count += len(dirs)

        for f in files:
            try:
                fp = Path(root) / f
                stat = fp.stat()
                file_count += 1
                size = stat.st_size
                total_size += size
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime)

                # Track file dates
                if earliest is None or mtime < earliest:
                    earliest = mtime
                if latest is None or mtime > latest:
                    latest = mtime

                # Track file types
                ext = fp.suffix.lower()
                if ext:
                    file_types[ext] = file_types.get(ext, 0) + 1

                # Track largest files
                largest_files.append((fp.relative_to(source_path), size))
                largest_files = sorted(largest_files, key=lambda x: x[1], reverse=True)[
                    :10
                ]

            except Exception:
                # Skip files we can't access
                continue

    # Get system and user info
    try:
        system_info = {
            "os": platform.system(),
            "hostname": platform.node(),
            "username": getpass.getuser(),
        }
    except Exception as e:
        system_info = {"note": f"System info collection failed: {e}"}

    # Summarize file types
    top_file_types = sorted(
        [(ext, count) for ext, count in file_types.items()],
        key=lambda x: x[1],
        reverse=True,
    )[:10]

    return {
        "file_count": file_count,
        "directory_count": dir_count,
        "total_size_bytes": total_size,
        "total_size_gb": round(total_size / (1024**3), 2),
        "total_size_human": get_human_size(total_size),
        "earliest_date": earliest.strftime("%Y-%m-%d %H:%M:%S") if earliest else "N/A",
        "latest_date": latest.strftime("%Y-%m-%d %H:%M:%S") if latest else "N/A",
        "top_file_types": top_file_types,
        "largest_files": [
            (str(path), get_human_size(size)) for path, size in largest_files
        ],
        "system_info": system_info,
        "archive_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
