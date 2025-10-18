"""Formatting utilities for coldstore."""

import re


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
