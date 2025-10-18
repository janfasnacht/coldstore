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
from coldstore.core.inspector import ArchiveInspector
from coldstore.core.manifest import EventMetadata
from coldstore.core.scanner import FileScanner
from coldstore.core.verifier import ArchiveVerifier
from coldstore.utils.formatters import format_size, format_time, parse_size
from coldstore.utils.preview import display_dry_run_preview, generate_dry_run_preview
from coldstore.utils.progress import ProgressTracker

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
        typer.echo("   Fix: chmod +r <directory>", err=True)
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
            typer.echo(
                "   Try creating the parent directory manually or check permissions",
                err=True,
            )
            raise typer.Exit(1) from e
    elif not destination.is_dir():
        typer.echo(f"❌ Destination path is not a directory: {destination}", err=True)
        raise typer.Exit(1)

    # Check destination is writable
    if not destination.stat().st_mode & 0o200:  # Check write permission
        typer.echo(f"❌ Destination directory is not writable: {destination}", err=True)
        typer.echo("   Fix: chmod +w <directory>", err=True)
        raise typer.Exit(1)

    return source, destination


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
    # Dry-run mode
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview operation without creating files"),
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

    # === STEP 5.5: Handle dry-run mode ===
    if dry_run:
        # Generate and display preview without creating any files
        preview = generate_dry_run_preview(
            scanner=scanner,
            source=source,
            destination=destination,
            archive_filename=archive_filename,
            compression_level=compression_level,
            milestone=milestone,
            exclude_patterns=list(exclude) if exclude else None,
        )

        display_dry_run_preview(preview)

        # Exit successfully without creating archive
        raise typer.Exit(0)

    # === STEP 6: Create archive with ArchiveBuilder ===
    try:
        typer.echo("📦 Creating archive...")
        typer.echo("")

        # Initialize progress tracker
        progress_tracker = None
        if logger.level <= logging.INFO:
            progress_tracker = ProgressTracker(
                total_items=counts["total"],
                total_bytes=total_size,
                display_func=lambda msg, end="": typer.echo(msg, nl=(end != "")),
            )

            def progress_callback(
                items_processed: int,
                total_items: int,
                current_path: str,
                bytes_written: int,
            ):
                """Progress callback for ArchiveBuilder."""
                progress_tracker.update(
                    items_processed=items_processed,
                    bytes_processed=bytes_written,
                    current_item=current_path,
                )

        else:
            progress_callback = None

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
            progress_callback=progress_callback,
        )

        # Finish progress tracking
        if progress_tracker:
            progress_tracker.finish()

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
        typer.echo(f"   • Verify:  coldstore verify {archive_path}")
        typer.echo(f"   • Inspect: coldstore inspect {archive_path}")
        if result.get("sha256_file_path"):
            typer.echo("")
            typer.echo("   Or use standard tools:")
            typer.echo(f"   • shasum -c {result['sha256_file_path'].name}")
            typer.echo(f"   • tar -tzf {archive_filename} | head")
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
        typer.echo(
            "   Common causes: insufficient disk space, permission errors, or I/O failures",
            err=True,
        )
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
                    eta_str = format_time(eta_seconds)
                else:
                    eta_str = "calculating..."

                # Format elapsed time
                elapsed_str = format_time(elapsed)

                # Create progress bar
                bar_width = 20
                filled = int(bar_width * percentage / 100)
                bar = "█" * filled + "░" * (bar_width - filled)

                # Truncate filename if too long
                display_file = current_file
                if len(display_file) > 40:
                    display_file = "..." + display_file[-37:]

                # Display progress (overwrite previous line)
                progress_line = (
                    f"\r🔍 [{bar}] {percentage:5.1f}% "
                    f"({files_verified}/{total_files}) | "
                    f"Elapsed: {elapsed_str} | ETA: {eta_str}\n"
                    f"   Current: {display_file}"
                )
                typer.echo(progress_line, nl=False)

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


def display_verification_result(  # noqa: C901
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

        typer.echo(f"Duration:    {format_time(result.elapsed_seconds)}")

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

        typer.echo(f"Duration:    {format_time(result.elapsed_seconds)}")

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


@app.command()
def inspect(  # noqa: C901
    archive_path: Annotated[
        Path, typer.Argument(help="Path to archive file (.tar.gz)")
    ],
    # Display modes
    files: Annotated[
        bool,
        typer.Option("--files", help="Show detailed file listing"),
    ] = False,
    largest: Annotated[
        Optional[int],
        typer.Option("--largest", help="Show N largest files (default: 10)"),
    ] = None,
    stats: Annotated[
        bool,
        typer.Option("--stats", help="Show detailed statistics"),
    ] = False,
    # Filtering options (for --files mode)
    pattern: Annotated[
        Optional[str],
        typer.Option("--pattern", help="Filter files by glob pattern (e.g., '*.py')"),
    ] = None,
    min_size: Annotated[
        Optional[str],
        typer.Option("--min-size", help="Minimum file size (e.g., '1MB')"),
    ] = None,
    max_size: Annotated[
        Optional[str],
        typer.Option("--max-size", help="Maximum file size (e.g., '1GB')"),
    ] = None,
    limit: Annotated[
        Optional[int],
        typer.Option("--limit", help="Limit number of files shown (e.g., 100)"),
    ] = None,
    # Output format
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
):
    """Inspect archive contents and metadata without extraction.

    Provides quick insights into archive contents, file distributions,
    and embedded metadata without needing to extract the entire archive.

    Display Modes:
        - Summary (default): High-level overview of archive
        - Files (--files): Detailed file listing
        - Largest (--largest N): Show N largest files
        - Stats (--stats): Detailed statistics

    Examples:
        coldstore inspect archive.tar.gz
        coldstore inspect --files archive.tar.gz
        coldstore inspect --largest 20 archive.tar.gz
        coldstore inspect --json archive.tar.gz
    """
    # Validate archive path
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.exists():
        typer.echo(f"❌ Archive not found: {archive_path}", err=True)
        raise typer.Exit(1)

    # Parse size filters if provided
    min_size_bytes = None
    max_size_bytes = None

    if min_size:
        try:
            min_size_bytes = parse_size(min_size)
        except ValueError as e:
            typer.echo(f"❌ Invalid min-size format: {e}", err=True)
            typer.echo("   Example: --min-size 1MB or --min-size 500KB", err=True)
            raise typer.Exit(1) from None

    if max_size:
        try:
            max_size_bytes = parse_size(max_size)
        except ValueError as e:
            typer.echo(f"❌ Invalid max-size format: {e}", err=True)
            typer.echo("   Example: --max-size 10MB or --max-size 1GB", err=True)
            raise typer.Exit(1) from None

    # Create inspector
    try:
        inspector = ArchiveInspector(archive_path)
    except FileNotFoundError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1) from None

    # Determine display mode and output
    if json_output:
        # JSON output mode
        output_data = {}

        if files:
            file_list = inspector.file_listing(
                pattern=pattern,
                min_size=min_size_bytes,
                max_size=max_size_bytes,
                limit=limit,
            )
            output_data["files"] = file_list
        elif largest is not None:
            largest_list = inspector.largest_files(n=largest if largest > 0 else 10)
            output_data["largest_files"] = largest_list
        elif stats:
            statistics = inspector.statistics()
            output_data["statistics"] = statistics
        else:
            # Default: summary
            summary = inspector.summary()
            output_data = summary

        # Output JSON
        typer.echo(json.dumps(output_data, indent=2))

    else:
        # Human-readable output
        if files:
            display_file_listing(
                inspector,
                pattern=pattern,
                min_size=min_size_bytes,
                max_size=max_size_bytes,
                limit=limit,
            )
        elif largest is not None:
            display_largest_files(inspector, n=largest if largest > 0 else 10)
        elif stats:
            display_statistics(inspector)
        else:
            # Default: summary
            display_summary(inspector, archive_path)


def display_summary(inspector: ArchiveInspector, archive_path: Path):  # noqa: C901
    """Display archive summary in human-readable format.

    Args:
        inspector: ArchiveInspector instance
        archive_path: Path to archive
    """
    summary = inspector.summary()

    typer.echo("=" * 70)
    typer.echo("📦 Archive Inspection")
    typer.echo("=" * 70)

    # Archive info
    archive = summary.get("archive", {})
    typer.echo(f"Archive:     {archive.get('filename', 'Unknown')}")
    size_bytes = archive.get("size_bytes", 0)
    typer.echo(f"Size:        {format_size(size_bytes)}")

    if "created_utc" in archive:
        typer.echo(f"Created:     {archive['created_utc']}")
    if "id" in archive:
        typer.echo(f"Archive ID:  {archive['id']}")

    # Contents
    if "contents" in summary:
        contents = summary["contents"]
        typer.echo("")
        typer.echo("Contents:")

        if "message" in contents:
            typer.echo(f"  {contents['message']}")
        else:
            typer.echo(f"  Files:       {contents.get('files', 0)}")
            typer.echo(f"  Directories: {contents.get('directories', 0)}")
            if contents.get("symlinks", 0) > 0:
                typer.echo(f"  Symlinks:    {contents['symlinks']}")

    # Source info
    if "source" in summary:
        source = summary["source"]
        typer.echo("")
        typer.echo("Source:")
        typer.echo(f"  Path:        {source.get('root', 'Unknown')}")

        git = source.get("git", {})
        if git.get("present"):
            typer.echo("")
            typer.echo("  Git:")
            if git.get("commit"):
                commit_short = git["commit"][:8]
                typer.echo(f"    Commit:    {commit_short}")
            if git.get("branch"):
                typer.echo(f"    Branch:    {git['branch']}")
            if git.get("tag"):
                typer.echo(f"    Tag:       {git['tag']}")

            status = "Clean" if not git.get("dirty") else "Dirty (uncommitted changes)"
            typer.echo(f"    Status:    {status}")

    # Event info
    if "event" in summary:
        event = summary["event"]
        if event.get("name") or event.get("type"):
            typer.echo("")
            typer.echo("Event:")
            if event.get("type"):
                typer.echo(f"  Type:        {event['type']}")
            if event.get("name"):
                typer.echo(f"  Name:        {event['name']}")
            if event.get("notes"):
                typer.echo("  Notes:")
                for note in event["notes"]:
                    typer.echo(f"    - {note}")

    # Environment info
    if "environment" in summary:
        env = summary["environment"]
        typer.echo("")
        typer.echo("Environment:")

        system = env.get("system", {})
        typer.echo(f"  OS:          {system.get('os', 'Unknown')}")
        typer.echo(f"  Hostname:    {system.get('hostname', 'Unknown')}")

        tools = env.get("tools", {})
        if tools.get("coldstore_version"):
            typer.echo(f"  Coldstore:   {tools['coldstore_version']}")

    # Integrity info
    if "integrity" in summary:
        integrity = summary["integrity"]
        typer.echo("")
        typer.echo("Integrity:")

        archive_sha = integrity.get("archive_sha256")
        if archive_sha:
            typer.echo(f"  Archive SHA256:  {archive_sha[:16]}... ✅")
        else:
            typer.echo("  Archive SHA256:  Not available")

        filelist_sha = integrity.get("filelist_sha256")
        if filelist_sha:
            typer.echo(f"  FILELIST hash:   {filelist_sha[:16]}... ✅")

    # Compression info
    if "compression" in summary:
        compression = summary["compression"]
        typer.echo("")
        typer.echo("Compression:")

        compressed = compression["compressed_bytes"]
        uncompressed = compression["uncompressed_bytes"]
        ratio = compression["ratio_percent"]
        saved = compression["space_saved_bytes"]

        typer.echo(f"  Compressed:    {format_size(compressed)}")
        typer.echo(f"  Uncompressed:  {format_size(uncompressed)}")

        # Handle negative compression (expansion) gracefully
        if ratio < 0:
            # Expansion occurred (uncompressible data)
            expansion = abs(saved)
            typer.echo(f"  Ratio:         0% (uncompressible data)")
            typer.echo(f"  Note:          Archive is {format_size(expansion)} larger than source")
        elif ratio == 0:
            typer.echo(f"  Ratio:         0% (no compression)")
        else:
            typer.echo(f"  Ratio:         {ratio}% space saved")
            typer.echo(f"  Saved:         {format_size(saved)}")

    typer.echo("=" * 70)


def display_file_listing(  # noqa: C901
    inspector: ArchiveInspector,
    pattern: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    limit: Optional[int] = None,
):
    """Display detailed file listing.

    Args:
        inspector: ArchiveInspector instance
        pattern: Glob pattern filter
        min_size: Minimum file size in bytes
        max_size: Maximum file size in bytes
        limit: Maximum number of files to display
    """
    files = inspector.file_listing(
        pattern=pattern,
        min_size=min_size,
        max_size=max_size,
        limit=limit,
    )

    if not files:
        if not inspector.filelist:
            # No FILELIST available
            typer.echo("=" * 100)
            typer.echo("⚠️  File listing not available")
            typer.echo("=" * 100)
            typer.echo("")
            typer.echo("This archive does not contain a FILELIST with file metadata.")
            typer.echo("")
            typer.echo("To create archives with file listings, use:")
            typer.echo("  coldstore freeze <source> <destination>")
        else:
            # FILELIST exists but no matches
            typer.echo("No files found matching criteria.")
        return

    typer.echo("=" * 100)
    typer.echo("📄 File Listing")
    typer.echo("=" * 100)

    # Show filters if applied
    filters = []
    if pattern:
        filters.append(f"pattern: {pattern}")
    if min_size:
        filters.append(f"min size: {format_size(min_size)}")
    if max_size:
        filters.append(f"max size: {format_size(max_size)}")
    if limit:
        filters.append(f"limit: {limit} files")

    if filters:
        typer.echo(f"Filters: {', '.join(filters)}")
        typer.echo("")

    # Header
    typer.echo(f"{'PATH':<60} {'SIZE':>12} {'TYPE':<8}")
    typer.echo("─" * 100)

    # Files
    for file_entry in files:
        path = file_entry["relpath"]
        file_type = file_entry["type"]
        size = file_entry.get("size_bytes")

        # Truncate long paths
        if len(path) > 58:
            display_path = "..." + path[-55:]
        else:
            display_path = path

        # Format size
        if size is not None:
            size_str = format_size(size)
        else:
            size_str = "-"

        typer.echo(f"{display_path:<60} {size_str:>12} {file_type:<8}")

    typer.echo("=" * 100)
    typer.echo(f"Total: {len(files)} items shown")

    if limit and len(files) == limit:
        typer.echo(f"Note: Output limited to {limit} files. Use --limit to show more.")


def display_largest_files(inspector: ArchiveInspector, n: int = 10):
    """Display largest files in archive.

    Args:
        inspector: ArchiveInspector instance
        n: Number of files to show
    """
    largest = inspector.largest_files(n=n)

    if not largest:
        typer.echo("=" * 80)
        typer.echo("⚠️  No file size information available")
        typer.echo("=" * 80)
        typer.echo("")
        typer.echo("This archive does not contain a FILELIST with file metadata.")
        typer.echo("")
        typer.echo("To create archives with complete metadata, use:")
        typer.echo("  coldstore freeze <source> <destination>")
        typer.echo("")
        typer.echo("This will generate:")
        typer.echo("  • MANIFEST.json with archive metadata")
        typer.echo("  • FILELIST.csv.gz with per-file details")
        typer.echo("  • SHA256 checksums for verification")
        return

    typer.echo("=" * 80)
    typer.echo(f"📊 Top {len(largest)} Largest Files")
    typer.echo("=" * 80)
    typer.echo("")

    total_size = 0
    for i, file_entry in enumerate(largest, 1):
        path = file_entry["relpath"]
        size = file_entry["size_bytes"]
        total_size += size

        # Format output
        size_str = format_size(size)
        typer.echo(f"{i:3d}.  {size_str:>10}  {path}")

    typer.echo("")
    typer.echo("─" * 80)
    typer.echo(f"Total size of top {len(largest)} files: {format_size(total_size)}")
    typer.echo("=" * 80)


def display_statistics(inspector: ArchiveInspector):
    """Display detailed archive statistics.

    Args:
        inspector: ArchiveInspector instance
    """
    stats = inspector.statistics()

    if not stats:
        typer.echo("=" * 80)
        typer.echo("⚠️  No statistics available")
        typer.echo("=" * 80)
        typer.echo("")
        typer.echo("This archive does not contain a FILELIST with per-file metadata.")
        typer.echo("")
        typer.echo("To create archives with complete metadata for statistics, use:")
        typer.echo("  coldstore freeze <source> <destination>")
        typer.echo("")
        typer.echo("Statistics available with FILELIST:")
        typer.echo("  • File type distribution (by extension)")
        typer.echo("  • Size distribution (bucketed by file size)")
        typer.echo("  • Directory sizes (top-level directories)")
        return

    typer.echo("=" * 80)
    typer.echo("📊 Archive Statistics")
    typer.echo("=" * 80)
    typer.echo("")

    # File types
    if "file_types" in stats:
        file_types = stats["file_types"]
        typer.echo("File Types:")
        typer.echo("")

        # Sort by size
        sorted_types = sorted(
            file_types.items(),
            key=lambda x: x[1]["size_bytes"],
            reverse=True,
        )

        for ext, data in sorted_types[:15]:  # Show top 15
            count = data["count"]
            size = data["size_bytes"]
            ext_display = f".{ext}" if ext != "(no extension)" else ext
            typer.echo(f"  {ext_display:<20} {count:>6} files  {format_size(size):>10}")

        typer.echo("")

    # Size distribution
    if "size_distribution" in stats:
        size_dist = stats["size_distribution"]
        typer.echo("Size Distribution:")
        typer.echo("")

        for bucket, count in size_dist.items():
            typer.echo(f"  {bucket:<15} {count:>6} files")

        typer.echo("")

    # Top directories
    if "directory_sizes" in stats:
        dir_sizes = stats["directory_sizes"]
        if dir_sizes:
            typer.echo("Top Directories by Size:")
            typer.echo("")

            for dir_name, size in dir_sizes.items():
                typer.echo(f"  {dir_name:<30} {format_size(size):>10}")

    typer.echo("=" * 80)


if __name__ == "__main__":
    app()
