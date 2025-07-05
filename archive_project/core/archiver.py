"""Core archiving functionality for archive_project."""

import datetime
import fnmatch
import hashlib
import shutil
import tarfile
from pathlib import Path
from typing import List, Optional, Tuple

from .metadata import get_metadata
from ..storage.rclone import upload_files
from ..utils.file_ops import get_file_tree, file_tree_fallback
from ..utils.formatters import generate_readme, get_human_size


def archive_project(
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
    exclude_patterns: Optional[List[str]] = None
) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """Archive a directory with enhanced features.
    
    Args:
        source_path: Path to source directory to archive
        archive_dir: Directory to store archive and metadata
        note: Optional note for README
        archive_name: Optional custom name for archive (defaults to source_name_timestamp)
        remote_path: Remote storage path
        storage_provider: Storage provider to use
        do_archive: Whether to create tar.gz archive
        do_upload: Whether to upload to remote storage
        delete_after_archive: Whether to delete original after archiving
        force: Skip confirmation prompts
        compress_level: Compression level (1-9)
        exclude_patterns: List of patterns to exclude from archive
        
    Returns:
        Tuple of (archive_path, sha256_path, readme_path)
    """
    # File path handling
    source_path = Path(source_path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")
    
    source_name = source_path.name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Use custom archive name if provided, otherwise default to source_name_timestamp
    if archive_name:
        base_name = archive_name
    else:
        base_name = f"{source_name}_{timestamp}"

    archive_dir = Path(archive_dir).expanduser().resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{base_name}.tar.gz"
    sha256_path = archive_dir / f"{base_name}.tar.gz.sha256"
    readme_path = archive_dir / f"{base_name}.README.md"

    # Collect metadata first (to estimate time required)
    print(f"📊 Collecting metadata for {source_path}...")
    meta = get_metadata(source_path)
    size_human = meta.get('total_size_human', meta['total_size_gb'])
    print(f"Found {meta['file_count']} files ({size_human}).")
    
    # Warn about large archives
    size_gb = meta.get('total_size_gb', 0)
    if size_gb > 10:
        print(f"⚠️  Large archive detected ({size_human}). This may take a while to compress and transfer.")
    if size_gb > 50:
        print(f"💡 Consider using --split-size option for archives this large (not yet implemented).")

    # Generate file tree (with fallback)
    try:
        print("🌳 Generating directory structure...")
        file_tree = get_file_tree(source_path)
        if "Could not generate file tree" in file_tree:
            file_tree = file_tree_fallback(source_path)
    except Exception as e:
        print(f"Warning: Could not generate directory structure: {e}")
        file_tree = f"Error generating directory structure: {e}"

    # Create archive if requested
    sha256_hash = None
    if do_archive:
        print(f"📦 Creating archive: {archive_path}")
        try:
            # Filter function for exclusions
            def filter_func(tarinfo):
                if exclude_patterns:
                    name = tarinfo.name
                    for pattern in exclude_patterns:
                        if fnmatch.fnmatch(name, pattern):
                            print(f"  Excluding: {name}")
                            return None
                return tarinfo

            with tarfile.open(archive_path, f"w:gz", compresslevel=compress_level) as tar:
                tar.add(source_path, arcname=source_name, filter=filter_func)

            # Calculate checksum with progress indicator
            print("🔐 Calculating SHA256 checksum...")
            sha256_hash = hashlib.sha256()
            total_size = archive_path.stat().st_size
            bytes_read = 0
            last_progress = 0

            with open(archive_path, "rb") as f:
                for byte_block in iter(lambda: f.read(65536), b""):  # Larger chunks for better performance
                    sha256_hash.update(byte_block)
                    bytes_read += len(byte_block)
                    # Update progress every 5%
                    if total_size > 0:
                        progress = int(bytes_read / total_size * 100)
                        if progress > last_progress and progress % 5 == 0:
                            print(f"  Progress: {progress}%", end="\r")
                            last_progress = progress

            sha256_hex = sha256_hash.hexdigest()
            print(f"\n✅ Checksum complete: {sha256_hex}")
            with open(sha256_path, "w") as f:
                f.write(f"{sha256_hex}  {archive_path.name}\n")
        except Exception as e:
            print(f"❌ Error creating archive: {e}")
            if not force:
                return None, None, None
    else:
        archive_path = None
        sha256_path = None
        sha256_hex = None

    # Generate and write README
    print("📄 Writing metadata...")
    readme_contents = generate_readme(
        base_name, source_name, str(source_path), timestamp,
        meta, file_tree, sha256_hex, note
    )

    with open(readme_path, "w") as f:
        f.write(readme_contents)

    print(f"\n✅ Metadata written to: {readme_path}")
    if sha256_path:
        print(f"✅ SHA256 saved to: {sha256_path}")
    if archive_path:
        print(f"✅ Archive created: {archive_path} ({get_human_size(archive_path.stat().st_size)})")

    # Upload files if requested
    if do_upload and remote_path:
        files_to_upload = [p for p in [archive_path, sha256_path, readme_path] if p]
        results = upload_files(
            files_to_upload,
            remote_path,
            storage_provider=storage_provider
        )

        success_count = sum(1 for r in results.values() if r["success"])
        print(f"\n☁️  Upload complete: {success_count}/{len(files_to_upload)} files uploaded successfully")

    # Delete original if requested
    if delete_after_archive and archive_path and archive_path.exists():
        print(f"\n🗑️  Archive complete. Preparing to delete original directory: {source_path}")
        if not force:
            confirm = input(f"Are you sure you want to permanently delete {source_path}? [y/N]: ").strip().lower()
            if confirm != "y":
                print("🛑 Deletion cancelled.")
                return archive_path, sha256_path, readme_path

        try:
            shutil.rmtree(source_path)
            print(f"🗑️  Deleted original directory: {source_path}")
        except Exception as e:
            print(f"❌ Failed to delete directory: {e}")

    return archive_path, sha256_path, readme_path