"""Command-line interface for archive_project."""

import argparse
import os
import sys
from pathlib import Path

from ..core.archiver import archive_project


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Coldstore - Archive directories to cold storage with comprehensive metadata.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Required arguments
    parser.add_argument("source_path", help="Path to the source directory to archive")
    parser.add_argument("archive_dir", help="Directory where the archive and metadata will be stored")

    # Basic options
    parser.add_argument("--note", help="Optional note or description for the archive", default=None)
    parser.add_argument("--name", help="Custom name for the archive (default: source_name_timestamp)", default=None)
    parser.add_argument("--no-archive", action="store_true", help="Skip creating the .tar.gz archive")
    parser.add_argument("--delete-after-archive", action="store_true", help="Delete original directory after archiving")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")

    # Compression options
    parser.add_argument("--compress-level", type=int, choices=range(1, 10), default=6,
                        help="Compression level (1=fastest, 9=smallest)")
    parser.add_argument("--exclude", action="append", default=[],
                        help="Exclude patterns (can be used multiple times)")

    # Upload options
    upload_group = parser.add_argument_group("Upload Options")
    upload_group.add_argument("--upload", action="store_true", help="Upload the files to remote storage")
    upload_group.add_argument("--remote-path", help="Remote storage destination path", default=None)
    upload_group.add_argument("--storage-provider", choices=["rclone", "aws", "gcp", "azure"],
                              default="rclone", help="Storage provider to use")

    # Parse and validate
    args = parser.parse_args()

    # Validate arguments
    if args.upload and not args.remote_path:
        parser.error("--upload requires --remote-path")

    # Create archive directory
    archive_dir = Path(args.archive_dir).expanduser().resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Run the archiver
    try:
        archive_project(
            Path(args.source_path),
            archive_dir,
            note=args.note,
            archive_name=args.name,
            remote_path=args.remote_path,
            storage_provider=args.storage_provider,
            do_archive=not args.no_archive,
            do_upload=args.upload,
            delete_after_archive=args.delete_after_archive,
            force=args.force,
            compress_level=args.compress_level,
            exclude_patterns=args.exclude
        )
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if os.environ.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()