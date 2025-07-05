"""Core archiving functionality for coldstore."""

import datetime
import fnmatch
import shutil
import tarfile
from pathlib import Path
from typing import Optional

from ..storage.rclone import upload_files
from ..utils.file_ops import get_file_tree
from ..utils.formatters import generate_readme, get_human_size
from .checksums import calculate_checksums_for_parts, write_sha256_file
from .metadata import get_metadata
from .splitter import create_split_archives


def setup_archive_paths(
    source_path: Path, archive_dir: Path, archive_name: Optional[str]
) -> tuple[Path, str, str, Path, Path, Path]:
    """Setup file paths and names for archiving."""
    source_path = Path(source_path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")

    source_name = source_path.name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d")

    if archive_name:
        base_name = archive_name
    else:
        base_name = f"{source_name}_{timestamp}"

    archive_dir = Path(archive_dir).expanduser().resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{base_name}.tar.gz"
    sha256_path = archive_dir / f"{base_name}.tar.gz.sha256"
    readme_path = archive_dir / f"{base_name}.README.md"

    return source_path, source_name, base_name, archive_path, sha256_path, readme_path


def collect_metadata_and_warn(source_path: Path, split_size: Optional[str] = None) -> dict:
    """Collect metadata and warn about large archives."""
    print(f"📊 Collecting metadata for {source_path}...")
    meta = get_metadata(source_path)
    size_human = meta.get("total_size_human", meta["total_size_gb"])
    print(f"Found {meta['file_count']} files ({size_human}).")

    # Warn about large archives
    size_gb = meta.get("total_size_gb", 0)
    if size_gb > 10:
        print(
            f"⚠️  Large archive detected ({size_human}). "
            "This may take a while to compress and transfer."
        )
    # Only suggest split-size if not already using it and archive is very large
    if size_gb > 50 and not split_size:
        print(
            "💡 Consider using --split-size option for archives this large "
            "to create more manageable parts."
        )

    return meta


def generate_file_tree(source_path: Path) -> str:
    """Generate file tree with fallback."""
    try:
        print("🌳 Generating directory structure...")
        from ..utils.file_ops import file_tree_fallback

        file_tree = get_file_tree(source_path)
        if "Could not generate file tree" in file_tree:
            file_tree = file_tree_fallback(source_path)
        return file_tree
    except Exception as e:
        print(f"Warning: Could not generate directory structure: {e}")
        return f"Error generating directory structure: {e}"


def create_archives(
    source_path: Path,
    source_name: str,
    archive_path: Path,
    compress_level: int,
    exclude_patterns: Optional[list[str]],
    split_size: Optional[str] = None,
) -> list[Path]:
    """Create archive(s) - either single or split based on split_size."""
    try:
        if split_size:
            # Create split archives
            return create_split_archives(
                source_path, source_name, archive_path, compress_level,
                exclude_patterns, split_size
            )
        else:
            # Create single archive
            print(f"📦 Creating archive: {archive_path}")

            def filter_func(tarinfo):
                if exclude_patterns:
                    name = tarinfo.name
                    for pattern in exclude_patterns:
                        if fnmatch.fnmatch(name, pattern):
                            print(f"  Excluding: {name}")
                            return None
                return tarinfo

            with tarfile.open(
                archive_path, "w:gz", compresslevel=compress_level
            ) as tar:
                tar.add(source_path, arcname=source_name, filter=filter_func)

            return [archive_path]
    except Exception as e:
        print(f"❌ Error creating archive: {e}")
        raise


def handle_upload(
    archive_paths: list[Path],
    sha256_path: Optional[Path],
    readme_path: Path,
    remote_path: str,
    storage_provider: str,
) -> None:
    """Handle uploading all archive files to remote storage."""
    files_to_upload = []
    if archive_paths:
        files_to_upload.extend(archive_paths)
    if sha256_path:
        files_to_upload.append(sha256_path)
    files_to_upload.append(readme_path)

    if files_to_upload:
        results = upload_files(
            files_to_upload,
            remote_path,
            storage_provider=storage_provider,
        )
        success_count = sum(1 for r in results.values() if r["success"])
        total_files = len(files_to_upload)
        print(
            f"\n☁️  Upload complete: {success_count}/{total_files} "
            "files uploaded successfully"
        )


def delete_original_source(
    source_path: Path, archive_paths: list[Path], force: bool
) -> None:
    """Delete original directory after confirmation."""
    if not archive_paths or not any(p.exists() for p in archive_paths):
        return

    print(
        f"\n🗑️  Archive complete. Preparing to delete original "
        f"directory: {source_path}"
    )
    if not force:
        confirm = (
            input(
                f"Are you sure you want to permanently delete {source_path}? "
                "[y/N]: "
            )
            .strip()
            .lower()
        )
        if confirm != "y":
            print("🛑 Deletion cancelled.")
            return

    try:
        shutil.rmtree(source_path)
        print(f"🗑️  Deleted original directory: {source_path}")
    except Exception as e:
        print(f"❌ Failed to delete directory: {e}")


def create_coldstore_archive(
    source_path: Path,
    archive_dir: Path,
    note: Optional[str] = None,
    archive_name: Optional[str] = None,
    remote_path: Optional[str] = None,
    storage_provider: str = "rclone",
    do_archive: bool = True,
    do_upload: bool = False,
    delete_after_archive: bool = False,
    force: bool = False,
    compress_level: int = 6,
    exclude_patterns: Optional[list[str]] = None,
    split_size: Optional[str] = None,
) -> tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """Create a coldstore archive with enhanced features.

    Args:
        source_path: Path to source directory to archive
        archive_dir: Directory to store archive and metadata
        note: Optional note for README
        archive_name: Optional custom name for archive
            (defaults to source_name_timestamp)
        remote_path: Remote storage path
        storage_provider: Storage provider to use
        do_archive: Whether to create tar.gz archive
        do_upload: Whether to upload to remote storage
        delete_after_archive: Whether to delete original after archiving
        force: Skip confirmation prompts
        compress_level: Compression level (1-9)
        exclude_patterns: List of patterns to exclude from archive
        split_size: Split archives larger than this size (e.g., '2GB', '500MB')

    Returns:
        Tuple of (archive_path, sha256_path, readme_path)
    """
    # Setup paths and names
    source_path, source_name, base_name, archive_path, sha256_path, readme_path = (
        setup_archive_paths(source_path, archive_dir, archive_name)
    )

    # Collect metadata and warn about large archives
    meta = collect_metadata_and_warn(source_path, split_size)

    # Generate file tree
    file_tree = generate_file_tree(source_path)

    # Create archive if requested
    archive_paths = []
    master_hash = None

    if do_archive:
        archive_paths = create_archives(
            source_path, source_name, archive_path, compress_level,
            exclude_patterns, split_size
        )

        # Calculate checksums
        sha256_hashes = calculate_checksums_for_parts(archive_paths)
        master_hash = write_sha256_file(
            sha256_path, sha256_hashes, is_split=len(archive_paths) > 1
        )

        print(f"✅ Checksums complete. Master hash: {master_hash[:16]}...")

        # For backward compatibility, use first archive path
        if archive_paths:
            archive_path = archive_paths[0]
        else:
            archive_path = None
    else:
        archive_path = None
        sha256_path = None
        archive_paths = []

    # Generate and write README
    print("📄 Writing metadata...")

    # Add split archive info to metadata if applicable
    if len(archive_paths) > 1:
        split_info = {
            "is_split": True,
            "num_parts": len(archive_paths),
            "part_files": [p.name for p in archive_paths],
            "total_size": sum(p.stat().st_size for p in archive_paths),
        }
        meta["split_archive"] = split_info

    readme_contents = generate_readme(
        base_name,
        source_name,
        str(source_path),
        datetime.datetime.now().strftime("%Y-%m-%d"),
        meta,
        file_tree,
        master_hash,
        note,
    )

    with open(readme_path, "w") as f:
        f.write(readme_contents)

    print(f"\n✅ Metadata written to: {readme_path}")
    if sha256_path:
        print(f"✅ SHA256 saved to: {sha256_path}")

    if archive_paths:
        if len(archive_paths) == 1:
            archive_size = get_human_size(archive_paths[0].stat().st_size)
            print(f"✅ Archive created: {archive_paths[0]} ({archive_size})")
        else:
            total_size = sum(p.stat().st_size for p in archive_paths)
            total_human = get_human_size(total_size)
            print(
                f"✅ Split archive created: {len(archive_paths)} parts, "
                f"total {total_human}"
            )
            for i, part in enumerate(archive_paths, 1):
                part_size = get_human_size(part.stat().st_size)
                print(f"  Part {i}: {part.name} ({part_size})")

    # Upload files if requested
    if do_upload and remote_path:
        handle_upload(
            archive_paths, sha256_path, readme_path, remote_path, storage_provider
        )

    # Delete original if requested
    if delete_after_archive:
        delete_original_source(source_path, archive_paths, force)

    return archive_path, sha256_path, readme_path
