"""Typer-based CLI application for coldstore."""

import json
import logging
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer

from coldstore.core.archiver import ArchiveBuilder
from coldstore.core.manifest import EventMetadata
from coldstore.core.scanner import FileScanner
from coldstore.core.verifier import ArchiveVerifier

app = typer.Typer(
    name="coldstore",
    help="Event-driven project archival with comprehensive metadata",
    add_completion=False,
)


def version_callback(value: bool):
    """Display version and exit."""
    if value:
        typer.echo("coldstore v1.0.0-dev")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
):
    """Coldstore - Event-driven project archival system.

    Create immutable, verifiable snapshots of project state at significant
    moments. Captures not just files, but context: git state, environment,
    and the event that triggered this archive.
    """
    pass


def generate_archive_filename(custom_name: Optional[str] = None) -> str:
    """Generate archive filename (timestamp-based or custom).

    Default Format: coldstore_YYYY-MM-DD_HH-MM-SS_XXXXXX.tar.gz
        - Timestamp: UTC time when archive is created
        - Random suffix: 6 hex characters for uniqueness
        - Design: Sortable, collision-resistant, timezone-aware

    Args:
        custom_name: Optional custom name (will append .tar.gz if missing)

    Returns:
        Archive filename with .tar.gz extension

    Examples:
        >>> generate_archive_filename()
        'coldstore_2025-01-15_14-30-45_a3f2c1.tar.gz'

        >>> generate_archive_filename("my_project")
        'my_project.tar.gz'

        >>> generate_archive_filename("backup.tar.gz")
        'backup.tar.gz'
    """
    if custom_name:
        # Ensure .tar.gz extension
        if not custom_name.endswith(".tar.gz"):
            return f"{custom_name}.tar.gz"
        return custom_name

    # Generate timestamp-based name: coldstore_YYYY-MM-DD_HH-MM-SS_XXXXXX.tar.gz
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    random_suffix = secrets.token_hex(3)  # 6 hex characters
    return f"coldstore_{timestamp}_{random_suffix}.tar.gz"


def validate_paths(source: Path, destination: Path) -> tuple[Path, Path]:
    """Validate and resolve source and destination paths.

    Args:
        source: Source directory path
        destination: Destination directory path

    Returns:
        Tuple of (resolved_source, resolved_destination)

    Raises:
        typer.Exit: If validation fails
    """
    # Resolve and validate source
    try:
        source = source.expanduser().resolve()
    except (OSError, RuntimeError) as e:
        typer.echo(f"❌ Error resolving source path: {e}", err=True)
        raise typer.Exit(1) from e

    if not source.exists():
        typer.echo(f"❌ Source path does not exist: {source}", err=True)
        raise typer.Exit(1)

    if not source.is_dir():
        typer.echo(f"❌ Source path is not a directory: {source}", err=True)
        raise typer.Exit(1)

    # Check source is readable
    if not source.stat().st_mode & 0o400:  # Check read permission
        typer.echo(f"❌ Source directory is not readable: {source}", err=True)
        raise typer.Exit(1)

    # Resolve and validate destination
    try:
        destination = destination.expanduser().resolve()
    except (OSError, RuntimeError) as e:
        typer.echo(f"❌ Error resolving destination path: {e}", err=True)
        raise typer.Exit(1) from e

    # Create destination if it doesn't exist
    if not destination.exists():
        try:
            destination.mkdir(parents=True, exist_ok=True)
            typer.echo(f"📁 Created destination directory: {destination}")
        except (OSError, PermissionError) as e:
            typer.echo(f"❌ Cannot create destination directory: {e}", err=True)
            raise typer.Exit(1) from e
    elif not destination.is_dir():
        typer.echo(f"❌ Destination path is not a directory: {destination}", err=True)
        raise typer.Exit(1)

    # Check destination is writable
    if not destination.stat().st_mode & 0o200:  # Check write permission
        typer.echo(f"❌ Destination directory is not writable: {destination}", err=True)
        raise typer.Exit(1)

    return source, destination


def format_size(bytes_: int) -> str:
    """Format bytes as human-readable size.

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


@app.command()
def freeze(  # noqa: C901
    source: Annotated[Path, typer.Argument(help="Source directory to archive")],
    destination: Annotated[
        Path, typer.Argument(help="Destination directory for archive and metadata")
    ],
    # Event metadata (optional but encouraged)
    milestone: Annotated[
        Optional[str],
        typer.Option(help="Event name (e.g., 'PNAS submission', 'v1.0 release')"),
    ] = None,
    note: Annotated[
        Optional[list[str]],
        typer.Option(help="Description note (repeatable)"),
    ] = None,
    contact: Annotated[
        Optional[list[str]],
        typer.Option(help="Contact info (repeatable)"),
    ] = None,
    # Output control
    compression_level: Annotated[
        int,
        typer.Option(
            min=1,
            max=9,
            help="Gzip compression level (1=fastest, 9=smallest)",
        ),
    ] = 6,
    name: Annotated[
        Optional[str],
        typer.Option(help="Custom archive name (overrides default timestamp-based)"),
    ] = None,
    # Filtering
    exclude: Annotated[
        Optional[list[str]],
        typer.Option(help="Exclude pattern (repeatable)"),
    ] = None,
    # Advanced toggles (rarely used)
    no_manifest: Annotated[
        bool,
        typer.Option("--no-manifest", help="Disable MANIFEST.json generation"),
    ] = False,
    no_filelist: Annotated[
        bool,
        typer.Option("--no-filelist", help="Disable FILELIST.csv.gz generation"),
    ] = False,
    no_sha256: Annotated[
        bool,
        typer.Option("--no-sha256", help="Disable SHA256 checksum computation"),
    ] = False,
    # Runtime options (hidden from help - for developers)
    log_level: Annotated[
        str,
        typer.Option(
            help="Logging level (debug, info, warn, error)",
            case_sensitive=False,
            hidden=True,  # Hide from --help
        ),
    ] = "info",
):
    """Create immutable archive with comprehensive metadata.

    Captures project state at significant moments: git state, environment,
    file checksums, and event context (milestone, notes, contacts).
    """
    # Configure logging
    log_level_upper = log_level.upper()
    if log_level_upper not in ["DEBUG", "INFO", "WARN", "WARNING", "ERROR"]:
        typer.echo(
            f"❌ Invalid log level: {log_level}. "
            "Must be debug, info, warn, or error.",
            err=True,
        )
        raise typer.Exit(1)

    # Map WARN to WARNING for Python logging
    if log_level_upper == "WARN":
        log_level_upper = "WARNING"

    logging.basicConfig(
        level=getattr(logging, log_level_upper),
        format="%(message)s",
    )

    logger = logging.getLogger(__name__)

    # === STEP 1: Validate paths ===
    try:
        source, destination = validate_paths(source, destination)
    except typer.Exit:
        raise  # Re-raise typer.Exit from validation

    # === STEP 2: Generate archive filename ===
    archive_filename = generate_archive_filename(name)
    archive_path = destination / archive_filename

    # Check if archive already exists
    if archive_path.exists():
        typer.echo(
            f"❌ Archive already exists: {archive_path}\n"
            "   Use a different --name or remove the existing archive.",
            err=True,
        )
        raise typer.Exit(1)

    # === STEP 3: Display operation summary ===
    typer.echo("=" * 60)
    typer.echo("📦 Coldstore - Creating Archive")
    typer.echo("=" * 60)
    typer.echo(f"Source:      {source}")
    typer.echo(f"Destination: {destination}")
    typer.echo(f"Archive:     {archive_filename}")

    if milestone:
        typer.echo(f"Event:       {milestone}")

    typer.echo(f"Compression: Level {compression_level}")

    if exclude:
        typer.echo(f"Exclusions:  {len(exclude)} pattern(s)")
        for pattern in exclude:
            typer.echo(f"             - {pattern}")

    # Show what's enabled/disabled
    features = []
    if not no_manifest:
        features.append("MANIFEST")
    if not no_filelist:
        features.append("FILELIST")
    if not no_sha256:
        features.append("SHA256")

    if features:
        typer.echo(f"Features:    {', '.join(features)}")

    disabled = []
    if no_manifest:
        disabled.append("MANIFEST")
    if no_filelist:
        disabled.append("FILELIST")
    if no_sha256:
        disabled.append("SHA256")

    if disabled:
        typer.echo(f"Disabled:    {', '.join(disabled)}")

    typer.echo("=" * 60)
    typer.echo("")

    # === STEP 4: Create EventMetadata ===
    event_metadata = EventMetadata(
        type="milestone" if milestone else None,
        name=milestone,
        notes=list(note) if note else [],
        contacts=list(contact) if contact else [],
    )

    # === STEP 5: Initialize FileScanner ===
    try:
        typer.echo("🔍 Scanning source directory...")
        scanner = FileScanner(
            source_root=source,
            exclude_patterns=list(exclude) if exclude else None,
            exclude_vcs=True,  # Always exclude VCS directories
            respect_gitignore=False,  # Don't respect .gitignore by default
        )

        # Count files for progress estimation
        counts = scanner.count_files()
        typer.echo(
            f"   Found {counts['files']} files, "
            f"{counts['dirs']} directories, "
            f"{counts['symlinks']} symlinks"
        )

        # Estimate size
        total_size = scanner.estimate_size()
        typer.echo(f"   Total size: {format_size(total_size)}")
        typer.echo("")

    except (OSError, PermissionError) as e:
        typer.echo(f"❌ Error scanning source directory: {e}", err=True)
        raise typer.Exit(1) from e

    # === STEP 6: Create archive with ArchiveBuilder ===
    try:
        typer.echo("📦 Creating archive...")

        # Progress tracking
        progress_counter = {"current": 0}

        def progress_callback(items_processed: int, total_items: int):
            """Simple progress callback."""
            progress_counter["current"] = items_processed
            # Only show progress every 10 items to avoid flooding output
            if items_processed % 10 == 0 or items_processed == total_items:
                percentage = (
                    (items_processed / total_items * 100) if total_items > 0 else 0
                )
                typer.echo(
                    f"   Progress: {items_processed}/{total_items} "
                    f"items ({percentage:.1f}%)"
                )

        # Initialize ArchiveBuilder
        builder = ArchiveBuilder(
            output_path=archive_path,
            compression_level=compression_level,
            compute_sha256=not no_sha256,
            generate_filelist=not no_filelist,
            generate_manifest=not no_manifest,
            event_metadata=event_metadata,
        )

        # Create the archive
        result = builder.create_archive(
            scanner=scanner,
            arcname_root=source.name,
            progress_callback=(
                progress_callback if logger.level <= logging.INFO else None
            ),
        )

        typer.echo("")
        typer.echo("=" * 60)
        typer.echo("✅ Archive created successfully!")
        typer.echo("=" * 60)
        typer.echo(f"Archive:     {result['path']}")
        typer.echo(f"Size:        {format_size(result['size_bytes'])}")
        typer.echo(
            f"Files:       {result['files_added']} files, "
            f"{result['dirs_added']} directories"
        )

        if result.get("sha256"):
            typer.echo(f"SHA256:      {result['sha256']}")

        if result.get("manifest_json_path"):
            typer.echo(f"Manifest:    {result['manifest_json_path']}")

        if result.get("sha256_file_path"):
            typer.echo(f"Checksum:    {result['sha256_file_path']}")

        typer.echo("=" * 60)
        typer.echo("")
        typer.echo("📝 Next steps:")
        if result.get("sha256_file_path"):
            typer.echo(f"   • Verify: shasum -c {result['sha256_file_path'].name}")
        typer.echo(f"   • Inspect: tar -tzf {archive_filename} | head")
        typer.echo("")

    except KeyboardInterrupt:
        typer.echo("\n❌ Operation cancelled by user", err=True)
        # Clean up partial archive
        if archive_path.exists():
            try:
                archive_path.unlink()
                typer.echo(f"🗑️  Removed partial archive: {archive_path}")
            except OSError:
                pass
        raise typer.Exit(130) from None  # 130 is standard exit code for SIGINT

    except Exception as e:
        typer.echo(f"\n❌ Error creating archive: {e}", err=True)
        logger.exception("Archive creation failed")
        # Clean up partial archive
        if archive_path.exists():
            try:
                archive_path.unlink()
                typer.echo(f"🗑️  Removed partial archive: {archive_path}")
            except OSError:
                pass
        raise typer.Exit(1) from e


@app.command()
def verify(  # noqa: C901
    archive_path: Annotated[
        Path, typer.Argument(help="Path to archive file (.tar.gz)")
    ],
    # Verification level
    deep: Annotated[
        bool,
        typer.Option(
            "--deep", help="Perform deep verification (verify per-file hashes)"
        ),
    ] = False,
    # Options
    manifest: Annotated[
        Optional[Path],
        typer.Option(
            help="Path to MANIFEST.json file (default: archive + .MANIFEST.json)"
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Suppress output except errors"),
    ] = False,
    fail_fast: Annotated[
        bool,
        typer.Option("--fail-fast", help="Stop at first error"),
    ] = False,
):
    """Verify archive integrity with multi-level checks.

    Verification Levels:
    - Quick (default): Archive hash, manifest validation, FILELIST hash
    - Deep (--deep): All quick checks + per-file hash verification

    Examples:
        coldstore verify archive.tar.gz
        coldstore verify --deep archive.tar.gz
        coldstore verify --json --quiet archive.tar.gz
    """
    # Validate archive path
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.exists():
        typer.echo(f"❌ Archive not found: {archive_path}", err=True)
        raise typer.Exit(1)

    # Create verifier
    try:
        verifier = ArchiveVerifier(
            archive_path=archive_path,
            manifest_path=manifest,
        )
    except FileNotFoundError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1) from None

    # Display header (unless quiet or JSON mode)
    if not quiet and not json_output:
        typer.echo("=" * 60)
        typer.echo("🔍 Coldstore - Verifying Archive")
        typer.echo("=" * 60)
        typer.echo(f"Archive:  {archive_path.name}")
        typer.echo(f"Level:    {'Deep' if deep else 'Quick'}")
        typer.echo("=" * 60)
        typer.echo("")

    # Perform verification
    time.time()

    if deep:
        # Deep verification with progress
        if not quiet and not json_output:
            # Progress tracking state
            progress_state = {
                "start_time": time.time(),
                "last_update": 0,
            }

            def progress_callback(
                files_verified: int, total_files: int, current_file: str
            ):
                """Display progress with ETA."""
                current_time = time.time()

                # Only update every 0.1 seconds to avoid flooding output
                if current_time - progress_state["last_update"] < 0.1:
                    return

                progress_state["last_update"] = current_time

                # Calculate progress
                percentage = (
                    (files_verified / total_files * 100) if total_files > 0 else 0
                )
                elapsed = current_time - progress_state["start_time"]

                # Calculate ETA
                if files_verified > 0:
                    avg_time_per_file = elapsed / files_verified
                    remaining_files = total_files - files_verified
                    eta_seconds = avg_time_per_file * remaining_files
                    eta_str = format_time_duration(eta_seconds)
                else:
                    eta_str = "calculating..."

                # Format elapsed time
                elapsed_str = format_time_duration(elapsed)

                # Create progress bar
                bar_width = 20
                filled = int(bar_width * percentage / 100)
                bar = "█" * filled + "░" * (bar_width - filled)

                # Truncate filename if too long
                display_file = current_file
                if len(display_file) > 40:
                    display_file = "..." + display_file[-37:]

                # Display progress (overwrite previous line)
                typer.echo(
                    f"\r🔍 [{bar}] {percentage:5.1f}% ({files_verified}/{total_files}) | "
                    f"Elapsed: {elapsed_str} | ETA: {eta_str}\n"
                    f"   Current: {display_file}",
                    nl=False,
                )

            result = verifier.verify_deep(
                progress_callback=progress_callback,
                fail_fast=fail_fast,
            )

            # Clear progress line
            typer.echo("\r" + " " * 120 + "\r", nl=False)
        else:
            result = verifier.verify_deep(fail_fast=fail_fast)
    else:
        # Quick verification
        result = verifier.verify_quick()

    # Output results
    if json_output:
        # JSON output mode
        output = result.to_dict()
        output["archive"] = str(archive_path)
        typer.echo(json.dumps(output, indent=2))
    elif not quiet:
        # Human-readable output
        display_verification_result(result, archive_path, deep)

    # Exit with appropriate code
    if result.passed:
        raise typer.Exit(0)
    else:
        raise typer.Exit(1)


def format_time_duration(seconds: float) -> str:
    """Format time duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2m 15s", "45s", "1h 23m")
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


def display_verification_result(
    result,
    archive_path: Path,
    deep_mode: bool,
):
    """Display verification result in human-readable format.

    Args:
        result: VerificationResult object
        archive_path: Path to archive
        deep_mode: Whether deep verification was performed
    """
    typer.echo("")
    typer.echo("=" * 60)

    if result.passed:
        typer.echo("✅ Verification successful!")
        typer.echo("=" * 60)
        typer.echo(f"Archive:     {archive_path.name}")
        typer.echo(f"Level:       {'Deep' if deep_mode else 'Quick'}")
        typer.echo(
            f"Checks:      {result.checks_passed}/{result.checks_performed} passed"
        )

        if deep_mode and result.files_verified is not None:
            typer.echo(f"Files:       {result.files_verified} verified")

            # Show bytes verified and throughput
            if result.bytes_verified is not None:
                if result.bytes_verified < 1024 * 1024:
                    size_str = f"{result.bytes_verified / 1024:.1f} KB"
                elif result.bytes_verified < 1024 * 1024 * 1024:
                    size_str = f"{result.bytes_verified / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{result.bytes_verified / (1024 * 1024 * 1024):.2f} GB"
                typer.echo(f"Data:        {size_str}")

            throughput = result.get_throughput_mbps()
            if throughput:
                typer.echo(f"Throughput:  {throughput:.1f} MB/s")

        typer.echo(f"Duration:    {format_time_duration(result.elapsed_seconds)}")

        if result.warnings:
            typer.echo("")
            typer.echo("⚠️  Warnings:")
            for warning in result.warnings:
                typer.echo(f"   • {warning}")

        typer.echo("=" * 60)
        typer.echo("")
        typer.echo("All checks passed. Archive is intact and verifiable.")

    else:
        typer.echo("❌ Verification failed!")
        typer.echo("=" * 60)
        typer.echo(f"Archive:     {archive_path.name}")
        typer.echo(f"Level:       {'Deep' if deep_mode else 'Quick'}")
        typer.echo(
            f"Checks:      {result.checks_passed}/{result.checks_performed} passed"
        )

        if deep_mode and result.files_verified is not None:
            typer.echo(f"Files:       {result.files_verified} verified")

            # Show bytes verified even on failure
            if result.bytes_verified is not None:
                if result.bytes_verified < 1024 * 1024:
                    size_str = f"{result.bytes_verified / 1024:.1f} KB"
                elif result.bytes_verified < 1024 * 1024 * 1024:
                    size_str = f"{result.bytes_verified / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{result.bytes_verified / (1024 * 1024 * 1024):.2f} GB"
                typer.echo(f"Data:        {size_str}")

        typer.echo(f"Duration:    {format_time_duration(result.elapsed_seconds)}")

        typer.echo("")
        typer.echo("❌ Errors:")
        for error in result.errors:
            # Handle multi-line errors (indent continuation lines)
            lines = error.split("\n")
            typer.echo(f"   • {lines[0]}")
            for line in lines[1:]:
                typer.echo(f"     {line}")

        if result.warnings:
            typer.echo("")
            typer.echo("⚠️  Warnings:")
            for warning in result.warnings:
                typer.echo(f"   • {warning}")

        typer.echo("=" * 60)
        typer.echo("")
        typer.echo(
            "⚠️  FATAL: Archive failed integrity check. Do not trust this archive."
        )


if __name__ == "__main__":
    app()
