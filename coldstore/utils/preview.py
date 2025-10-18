"""Dry-run preview generation for coldstore freeze operations."""

import gzip
import io
from pathlib import Path
from typing import Optional

from coldstore.core.scanner import FileScanner
from coldstore.metadata.git import collect_git_metadata

# Compression ratio estimates (fallback if sampling fails)
# Based on gzip compression of typical source code, documentation, and data files
COMPRESSION_RATIO_ESTIMATE = 0.45  # 45% of original size (55% compression)
COMPRESSION_RATIO_MIN = 0.35  # Best case: 65% compression
COMPRESSION_RATIO_MAX = 0.60  # Worst case: 40% compression

# Sampling configuration
DEFAULT_SAMPLE_TARGET_BYTES = 2 * 1024 * 1024  # 2 MB sample target
MIN_SAMPLE_BYTES = 100 * 1024  # 100 KB minimum for meaningful results
MAX_SAMPLE_BYTES = 10 * 1024 * 1024  # 10 MB maximum to keep it fast

# Time estimation heuristics (very rough estimates)
# Based on streaming tar+gzip write speed on modern hardware
BYTES_PER_SECOND_ESTIMATE = 50 * 1024 * 1024  # ~50 MB/s throughput
TIME_OVERHEAD_SECONDS = 5  # Base overhead for scanning, setup, etc.


def sample_compression_ratio(
    scanner: FileScanner,
    compression_level: int = 6,
    target_bytes: int = DEFAULT_SAMPLE_TARGET_BYTES,
) -> Optional[dict]:
    """
    Sample actual file data and compress it to determine real compression ratio.

    Reads a sample of actual file data (distributed across multiple files),
    compresses it with gzip at the specified level, and returns the actual
    compression ratio achieved.

    Strategy:
    - Collect files until we reach target_bytes of uncompressed data
    - Distribute sampling across multiple files for representative sample
    - Skip very small files to avoid overhead
    - Compress sample with actual gzip at user's compression level
    - Return real compression ratio

    Args:
        scanner: FileScanner instance
        compression_level: Gzip compression level (1-9)
        target_bytes: Target sample size in bytes

    Returns:
        Dictionary with sampling results:
        - ratio: Actual compression ratio (compressed/uncompressed)
        - sample_size: Uncompressed bytes sampled
        - compressed_size: Compressed size of sample
        - files_sampled: Number of files included in sample
        Or None if sampling failed (no files, all inaccessible, etc.)
    """
    sample_data = io.BytesIO()
    bytes_sampled = 0
    files_sampled = 0

    # Collect sample data from files
    for path in scanner.scan():
        # Only sample regular files
        if not path.is_file() or path.is_symlink():
            continue

        # Stop if we have enough sample data
        if bytes_sampled >= target_bytes:
            break

        # Don't sample more than MAX_SAMPLE_BYTES
        if bytes_sampled >= MAX_SAMPLE_BYTES:
            break

        try:
            file_size = path.stat().st_size

            # Skip empty files
            if file_size == 0:
                continue

            # Read the file (or portion of it)
            bytes_to_read = min(file_size, target_bytes - bytes_sampled)

            with open(path, "rb") as f:
                chunk = f.read(bytes_to_read)
                sample_data.write(chunk)
                bytes_sampled += len(chunk)
                files_sampled += 1

        except OSError:
            # Skip files we can't read
            continue

    # Check if we have a meaningful sample
    if bytes_sampled < MIN_SAMPLE_BYTES:
        # Sample too small to be meaningful
        return None

    # Compress the sample data
    uncompressed_data = sample_data.getvalue()
    compressed_buffer = io.BytesIO()

    try:
        with gzip.GzipFile(
            fileobj=compressed_buffer,
            mode="wb",
            compresslevel=compression_level,
        ) as gz:
            gz.write(uncompressed_data)

        compressed_size = len(compressed_buffer.getvalue())
        ratio = compressed_size / bytes_sampled if bytes_sampled > 0 else 1.0

        return {
            "ratio": ratio,
            "sample_size": bytes_sampled,
            "compressed_size": compressed_size,
            "files_sampled": files_sampled,
        }

    except Exception:
        # Compression failed for some reason
        return None


def estimate_compressed_size(
    uncompressed_bytes: int,
    actual_ratio: Optional[float] = None,
) -> tuple[int, int, int]:
    """
    Estimate compressed archive size.

    If actual_ratio is provided (from sampling), uses that for estimation.
    Otherwise falls back to typical compression ratios for source code.

    Args:
        uncompressed_bytes: Total size of files to archive in bytes
        actual_ratio: Actual compression ratio from sampling (compressed/uncompressed)

    Returns:
        Tuple of (estimated_bytes, min_bytes, max_bytes)
    """
    if actual_ratio is not None:
        # Use sampled ratio for estimate
        estimated = int(uncompressed_bytes * actual_ratio)
        # Add ±15% margin for min/max
        min_size = int(estimated * 0.85)
        max_size = int(estimated * 1.15)
    else:
        # Fall back to heuristic ratios
        estimated = int(uncompressed_bytes * COMPRESSION_RATIO_ESTIMATE)
        min_size = int(uncompressed_bytes * COMPRESSION_RATIO_MIN)
        max_size = int(uncompressed_bytes * COMPRESSION_RATIO_MAX)

    return estimated, min_size, max_size


def estimate_time(uncompressed_bytes: int) -> tuple[int, int]:
    """
    Estimate archive creation time in seconds.

    Based on typical streaming tar+gzip write speeds.
    Very rough heuristic - actual time varies with:
    - File count (many small files slower than few large files)
    - Disk I/O speed
    - CPU compression speed
    - Compression level

    Args:
        uncompressed_bytes: Total size of files to archive in bytes

    Returns:
        Tuple of (estimated_seconds, max_seconds)
    """
    base_time = int(uncompressed_bytes / BYTES_PER_SECOND_ESTIMATE)
    estimated_seconds = base_time + TIME_OVERHEAD_SECONDS

    # Add 50% margin for max estimate
    max_seconds = int(estimated_seconds * 1.5)

    return estimated_seconds, max_seconds


def format_time_estimate(seconds: int) -> str:
    """
    Format time estimate as human-readable string.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string (e.g., "2m 15s", "45s", "1h 23m")
    """
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


def find_largest_files(scanner: FileScanner, n: int = 10) -> list[dict]:
    """
    Find the N largest files from scanner.

    Args:
        scanner: FileScanner instance
        n: Number of largest files to return

    Returns:
        List of dicts with {path, size_bytes} sorted by size (largest first)
    """
    files_with_sizes = []

    for path in scanner.scan():
        if path.is_file() and not path.is_symlink():
            try:
                size = path.stat().st_size
                rel_path = path.relative_to(scanner.source_root)
                files_with_sizes.append({"path": str(rel_path), "size_bytes": size})
            except OSError:
                # Skip files that can't be stat'd
                continue

    # Sort by size (descending) and take top N
    files_with_sizes.sort(key=lambda x: x["size_bytes"], reverse=True)
    return files_with_sizes[:n]


def generate_dry_run_preview(
    scanner: FileScanner,
    source: Path,
    destination: Path,
    archive_filename: str,
    compression_level: int,
    milestone: Optional[str] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> dict:
    """
    Generate dry-run preview data for freeze operation.

    Scans the filesystem and collects preview information without
    creating any files. Uses existing scanner methods and metadata
    collectors for consistency.

    Args:
        scanner: Initialized FileScanner instance
        source: Source directory path
        destination: Destination directory path
        archive_filename: Generated archive filename
        compression_level: Gzip compression level
        milestone: Optional event milestone name
        exclude_patterns: Optional list of exclusion patterns

    Returns:
        Dictionary with preview data:
        - counts: {files, dirs, symlinks, total}
        - sizes: {uncompressed, compressed_estimate, compressed_min, compressed_max}
        - largest_files: List of top 10 largest files
        - git: Git metadata dict
        - exclusions: List of applied exclusion patterns
        - output_files: Dict of would-be created files
        - time_estimate: {seconds, max_seconds, display}
    """
    # Get file counts
    counts = scanner.count_files()

    # Get total size
    uncompressed_size = scanner.estimate_size()

    # Sample compression ratio for accurate estimation
    sample_result = sample_compression_ratio(scanner, compression_level)

    # Estimate compressed size (using sampled ratio if available)
    if sample_result:
        actual_ratio = sample_result["ratio"]
        compressed_est, compressed_min, compressed_max = estimate_compressed_size(
            uncompressed_size, actual_ratio=actual_ratio
        )
    else:
        compressed_est, compressed_min, compressed_max = estimate_compressed_size(
            uncompressed_size
        )

    # Find largest files
    largest_files = find_largest_files(scanner, n=10)

    # Collect git metadata (will be minimal until issue #16 is implemented)
    git_metadata = collect_git_metadata(str(source))

    # Determine exclusion patterns
    exclusions = []
    if scanner.exclude_vcs:
        exclusions.append("VCS directories (.git/, .hg/, .svn/, .bzr/, CVS/)")
    if exclude_patterns:
        exclusions.extend(exclude_patterns)

    # Generate would-be output filenames
    output_files = {
        "archive": destination / archive_filename,
        "manifest_json": destination / f"{archive_filename}.MANIFEST.json",
        "sha256": destination / f"{archive_filename}.sha256",
    }

    # Estimate time
    time_est, time_max = estimate_time(uncompressed_size)

    # Format time range
    time_est_str = format_time_estimate(time_est)
    time_max_str = format_time_estimate(time_max)

    return {
        "source": source,
        "destination": destination,
        "milestone": milestone,
        "compression_level": compression_level,
        "counts": counts,
        "sizes": {
            "uncompressed_bytes": uncompressed_size,
            "compressed_estimate_bytes": compressed_est,
            "compressed_min_bytes": compressed_min,
            "compressed_max_bytes": compressed_max,
        },
        "sample": sample_result,  # Include sampling metadata
        "largest_files": largest_files,
        "git": git_metadata,
        "exclusions": exclusions,
        "output_files": output_files,
        "time_estimate": {
            "seconds": time_est,
            "max_seconds": time_max,
            "display": time_est_str,
            "display_range": f"{time_est_str}-{time_max_str}",
        },
    }


def format_size(bytes_: int) -> str:
    """
    Format bytes as human-readable size.

    Args:
        bytes_: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB", "42.3 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_ < 1024.0:
            if unit == "B":
                return f"{int(bytes_)} {unit}"
            return f"{bytes_:.1f} {unit}"
        bytes_ /= 1024.0
    return f"{bytes_:.1f} PB"


def _display_git_metadata(git: dict) -> None:
    """Display git metadata section of dry-run preview."""
    import typer

    if git and git.get("present"):
        typer.echo("Git metadata:")
        if git.get("commit"):
            typer.echo(f"  Commit:  {git['commit'][:12]}")
        if git.get("branch"):
            typer.echo(f"  Branch:  {git['branch']}")
        if git.get("tag"):
            typer.echo(f"  Tag:     {git['tag']}")

        dirty = git.get("dirty", False)
        typer.echo(f"  Dirty:   {dirty}")
        typer.echo("")
    else:
        typer.echo("Git metadata:")
        typer.echo("  Not available (source is not a git repository)")
        typer.echo("")


def _display_largest_files(largest: list[dict]) -> None:
    """Display largest files section of dry-run preview."""
    import typer

    if largest:
        typer.echo("Largest files:")
        for i, file_info in enumerate(largest, 1):
            path = file_info["path"]
            size = file_info["size_bytes"]
            # Truncate path if too long
            if len(path) > 50:
                display_path = "..." + path[-47:]
            else:
                display_path = path
            typer.echo(f"  {i:2d}. {display_path:<50} {format_size(size):>10}")
        typer.echo("")


def display_dry_run_preview(preview: dict) -> None:
    """
    Display dry-run preview in human-readable format.

    Matches the example output format from issue #5.

    Args:
        preview: Preview data dict from generate_dry_run_preview()
    """
    import typer

    counts = preview["counts"]
    sizes = preview["sizes"]
    largest = preview["largest_files"]
    git = preview["git"]
    exclusions = preview["exclusions"]
    outputs = preview["output_files"]
    time_est = preview["time_estimate"]

    # Header
    typer.echo("")
    typer.echo("=" * 70)
    typer.echo("🔍 DRY-RUN MODE - No files will be written")
    typer.echo("=" * 70)
    typer.echo("")

    # Source and destination
    typer.echo(f"Source:      {preview['source']}")
    typer.echo(f"Destination: {preview['destination']}")
    typer.echo("")

    # What would be archived
    typer.echo("Would archive:")
    typer.echo(f"  Files:       {counts['files']:,}")
    typer.echo(f"  Directories: {counts['dirs']:,}")
    if counts["symlinks"] > 0:
        typer.echo(f"  Symlinks:    {counts['symlinks']:,}")

    # Size estimates
    uncompressed = sizes["uncompressed_bytes"]
    compressed = sizes["compressed_estimate_bytes"]
    sample = preview.get("sample")

    typer.echo(f"  Total size:  {format_size(uncompressed)}")

    # Show compression estimate with sampling info
    if sample:
        sample_size = sample["sample_size"]
        compression_pct = (1 - sample["ratio"]) * 100
        typer.echo(
            f"               (estimated compressed: {format_size(compressed)}, "
            f"~{compression_pct:.0f}% compression)"
        )
        typer.echo(f"               [based on {format_size(sample_size)} sample]")
    else:
        typer.echo(f"               (estimated compressed: {format_size(compressed)})")

    typer.echo("")

    # Largest files
    _display_largest_files(largest)

    # Git metadata
    _display_git_metadata(git)

    # Exclusions
    if exclusions:
        typer.echo("Exclusions applied:")
        for pattern in exclusions:
            typer.echo(f"  - {pattern}")
        typer.echo("")

    # Event metadata
    if preview.get("milestone"):
        typer.echo("Event:")
        typer.echo(f"  Milestone: {preview['milestone']}")
        typer.echo("")

    # Output files
    typer.echo("Output would be:")
    typer.echo(f"  Archive:  {outputs['archive'].name}")
    typer.echo(f"  Manifest: {outputs['manifest_json'].name}")
    typer.echo(f"  Checksum: {outputs['sha256'].name}")
    typer.echo("")

    # Time estimate
    typer.echo(f"Estimated time: {time_est['display_range']}")
    typer.echo("")

    # Footer
    typer.echo("=" * 70)
    typer.echo("✅ Preview complete. Run without --dry-run to create archive.")
    typer.echo("=" * 70)
    typer.echo("")
