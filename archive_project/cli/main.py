"""Command-line interface for archive_project."""

import os
import sys
from pathlib import Path
from typing import List, Optional

import click

from ..core.archiver import archive_project


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("source_path", type=click.Path(exists=True, path_type=Path))
@click.argument("archive_dir", type=click.Path(path_type=Path))
@click.option("--note", help="Optional note or description for the archive")
@click.option("--name", help="Custom name for the archive (default: source_name_timestamp)")
@click.option("--no-archive", is_flag=True, help="Skip creating the .tar.gz archive")
@click.option("--delete-after-archive", is_flag=True, help="Delete original directory after archiving")
@click.option("--force", is_flag=True, help="Skip confirmation prompts")
@click.option("--compress-level", type=click.IntRange(1, 9), default=6, show_default=True,
              help="Compression level (1=fastest, 9=smallest)")
@click.option("--exclude", multiple=True, help="Exclude patterns (can be used multiple times)")
@click.option("--upload", is_flag=True, help="Upload the files to remote storage")
@click.option("--remote-path", help="Remote storage destination path")
@click.option("--storage-provider", type=click.Choice(["rclone", "aws", "gcp", "azure"]), 
              default="rclone", show_default=True, help="Storage provider to use")
def main(
    source_path: Path,
    archive_dir: Path,
    note: Optional[str],
    name: Optional[str],
    no_archive: bool,
    delete_after_archive: bool,
    force: bool,
    compress_level: int,
    exclude: List[str],
    upload: bool,
    remote_path: Optional[str],
    storage_provider: str
):
    """Coldstore - Archive directories to cold storage with comprehensive metadata.
    
    SOURCE_PATH is the path to the source directory to archive.
    ARCHIVE_DIR is the directory where the archive and metadata will be stored.
    """
    # Validate arguments
    if upload and not remote_path:
        raise click.ClickException("--upload requires --remote-path")

    # Create archive directory
    archive_dir = archive_dir.expanduser().resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Run the archiver
    try:
        archive_project(
            source_path,
            archive_dir,
            note=note,
            archive_name=name,
            remote_path=remote_path,
            storage_provider=storage_provider,
            do_archive=not no_archive,
            do_upload=upload,
            delete_after_archive=delete_after_archive,
            force=force,
            compress_level=compress_level,
            exclude_patterns=list(exclude)
        )
    except KeyboardInterrupt:
        click.echo("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        if os.environ.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()