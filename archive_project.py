import os
import subprocess
import hashlib
import tarfile
import datetime
from pathlib import Path
import argparse
import shutil
import sys
import fnmatch


def get_metadata(project_path):
    """Enhanced metadata collection with additional useful information."""
    file_count = 0
    dir_count = 0
    total_size = 0
    earliest = None
    latest = None
    file_types = {}
    largest_files = []

    for root, dirs, files in os.walk(project_path):
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
                largest_files.append((fp.relative_to(project_path), size))
                largest_files = sorted(largest_files, key=lambda x: x[1],
                                       reverse=True)[:10]

            except Exception as e:
                continue

    # Get system and user info
    try:
        import platform
        import getpass
        system_info = {
            "os": platform.system(),
            "hostname": platform.node(),
            "username": getpass.getuser()
        }
    except Exception as e:
        system_info = {"note": f"System info collection failed: {e}"}

    # Summarize file types
    top_file_types = sorted([(ext, count) for ext, count in file_types.items()],
                            key=lambda x: x[1], reverse=True)[:10]

    return {
        "file_count": file_count,
        "directory_count": dir_count,
        "total_size_bytes": total_size,
        "total_size_gb": round(total_size / (1024**3), 2),
        "total_size_human": get_human_size(total_size),
        "earliest_date": earliest.strftime("%Y-%m-%d %H:%M:%S") if earliest else "N/A",
        "latest_date": latest.strftime("%Y-%m-%d %H:%M:%S") if latest else "N/A",
        "top_file_types": top_file_types,
        "largest_files": [(str(path), get_human_size(size)) for path, size in largest_files],
        "system_info": system_info,
        "archive_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def get_human_size(size_bytes):
    """Convert byte size to human readable format."""
    if size_bytes == 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {units[i]}"


def get_file_tree(project_path, depth=2):
    try:
        result = subprocess.run(
            ["tree", f"-L{depth}", "--noreport", str(project_path)],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        # Replace with a pure Python implementation
        return file_tree_fallback(project_path, depth)  # New function


def upload_files(files, destination, storage_provider="rclone",
                 progress_callback=None):
    """
    Generic file upload function supporting multiple cloud storage providers.

    Args:
        files: List of file paths to upload
        destination: Destination path/URL
        storage_provider: Which tool/method to use ("rclone", [more to come])
        progress_callback: Optional callback function for progress updates

    Returns:
        dict: Results for each file
    """
    results = {}

    for f in files:
        if not f or not Path(f).exists():
            continue

        print(f"Uploading {f}...")

        if storage_provider == "rclone":
            cmd = ["rclone", "copy", str(f), destination, "--progress"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                success = result.returncode == 0
                results[f] = {
                    "success": success,
                    "error": result.stderr if not success else None
                }
                if not success:
                    print(f"❌ Error uploading {Path(f).name}: {result.stderr}")
                else:
                    print(f"✅ Uploaded: {Path(f).name}")
            except Exception as e:
                results[f] = {"success": False, "error": str(e)}
                print(f"❌ Exception during upload of {Path(f).name}: {e}")

        else:
            # no other providers implemented yet
            results[f] = {"success": False, "error": "Provider not supported"}
            print(f"❌ Provider not supported: {storage_provider}")

        # Call progress callback if provided
        if progress_callback:
            progress_callback(f, results[f]["success"])

    return results


def file_tree_fallback(dir_path, max_depth=2, prefix=""):
    """
    Generate a file tree structure similar to the 'tree' command without external dependencies.

    Args:
        dir_path: Path to directory
        max_depth: Maximum depth to traverse
        prefix: String prefix for current line (used recursively)

    Returns:
        String representation of the file tree
    """
    if max_depth < 0:
        return ""

    dir_path = Path(dir_path)
    output = [f"{prefix}{dir_path.name}"]

    try:
        items = sorted(list(dir_path.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return f"{prefix}{dir_path.name} [Permission Denied]"

    # Count files and directories for summary
    count = {"dirs": 0, "files": 0}

    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        item_prefix = prefix + ("└── " if is_last else "├── ")
        next_prefix = prefix + ("    " if is_last else "│   ")

        if item.is_dir():
            count["dirs"] += 1
            if max_depth > 0:
                subtree = file_tree_fallback(item, max_depth - 1, next_prefix)
                output.append(f"{item_prefix}{item.name}")
                output.append(subtree)
            else:
                output.append(f"{item_prefix}{item.name}")
        else:
            count["files"] += 1
            output.append(f"{item_prefix}{item.name}")

    return "\n".join(output)


def generate_readme(base_name, project_name, project_path, timestamp, meta,
                    file_tree, sha256_hash=None, note=None):
    """Generate a comprehensive README with enhanced metadata."""

    file_types_section = ""
    if meta.get("top_file_types"):
        file_types_section = "## File Types\n\n"
        for ext, count in meta["top_file_types"]:
            file_types_section += f"- {ext}: {count} files\n"

    large_files_section = ""
    if meta.get("largest_files"):
        large_files_section = "## Largest Files\n\n"
        for path, size in meta["largest_files"]:
            large_files_section += f"- {path}: {size}\n"

    system_info = meta.get("system_info", {})

    return f"""# Archive: {base_name}

## Project Information
- Project: `{project_name}`
- Archived from: `{project_path}`
- Archive date: {timestamp}
- Created by: {system_info.get('username', 'Unknown')} on {system_info.get('hostname', 'Unknown')} ({system_info.get('os', 'Unknown')})

## Contents Summary
- Files: {meta['file_count']}
- Directories: {meta.get('directory_count', 'N/A')}
- Total size: {meta.get('total_size_human', meta['total_size_gb'])}
- Data range: {meta['earliest_date']} to {meta['latest_date']}
{f'- SHA256: `{sha256_hash.hexdigest()}`' if sha256_hash else ''}

## Notes
{note or "(No additional notes provided)"}

{file_types_section}
{large_files_section}
## File Tree (up to 2 levels)

```text
{file_tree}
```

---
Created with archive_project.py on {meta.get('archive_date', timestamp)}
https://github.com/janfasnacht/tools/archive_project
"""


def archive_project(project_path, archive_dir, note=None, remote_path=None,
                    storage_provider="rclone", do_archive=True, do_upload=False,
                    delete_after_archive=False, force=False, compress_level=6,
                    exclude_patterns=None):
    """
    Archive a project with enhanced features.

    Args:
        project_path: Path to project directory
        archive_dir: Directory to store archive and metadata
        note: Optional note for README
        remote_path: Remote storage path
        storage_provider: Storage provider to use
        do_archive: Whether to create tar.gz archive
        do_upload: Whether to upload to remote storage
        delete_after_archive: Whether to delete original after archiving
        force: Skip confirmation prompts
        compress_level: Compression level (1-9)
        exclude_patterns: List of patterns to exclude from archive

    Returns:
        Tuple of created file paths
    """
    # File path handling
    project_path = Path(project_path).expanduser().resolve()
    if not project_path.exists():
        raise FileNotFoundError(f"Project path not found: {project_path}")
    project_name = project_path.name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
    base_name = f"{project_name}_{timestamp}"

    archive_dir = Path(archive_dir).expanduser().resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{base_name}.tar.gz"
    sha256_path = archive_dir / f"{base_name}.tar.gz.sha256"
    readme_path = archive_dir / f"{base_name}.README.md"

    # Collect metadata first (to estimate time required)
    print(f"📊 Collecting metadata for {project_path}...")
    meta = get_metadata(project_path)
    print(f"Found {meta['file_count']} files ({meta.get('total_size_human', meta['total_size_gb'])}).")

    # Generate file tree (with fallback)
    try:
        print(f"🌳 Generating file tree...")
        file_tree = get_file_tree(project_path)
        if "Could not generate file tree" in file_tree:
            file_tree = file_tree_fallback(project_path)
    except Exception as e:
        print(f"Warning: Could not generate file tree: {e}")
        file_tree = f"Error generating file tree: {e}"

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
                tar.add(project_path, arcname=project_name, filter=filter_func)

            # Calculate checksum with progress indicator
            print(f"🔐 Calculating SHA256 checksum...")
            sha256_hash = hashlib.sha256()
            total_size = archive_path.stat().st_size
            bytes_read = 0

            with open(archive_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
                    bytes_read += len(byte_block)
                    # Update progress every ~5%
                    if bytes_read % (total_size // 20) < 4096:
                        progress = bytes_read / total_size * 100
                        print(f"  Progress: {progress:.1f}%", end="\r")

            print(f"✅ Checksum complete: {sha256_hash.hexdigest()}")
            with open(sha256_path, "w") as f:
                f.write(f"{sha256_hash.hexdigest()}  {archive_path.name}\n")
        except Exception as e:
            print(f"❌ Error creating archive: {e}")
            if not force:
                return None, None, None
    else:
        archive_path = None
        sha256_path = None

    # Generate and write README
    print("🧾 Writing metadata...")
    readme_contents = generate_readme(
        base_name, project_name, project_path, timestamp,
        meta, file_tree, sha256_hash, note
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
        print(f"\n☁️ Upload complete: {success_count}/{len(files_to_upload)} files uploaded successfully")

    # Delete original if requested
    if delete_after_archive and archive_path and archive_path.exists():
        print(f"\n🧨 Archive complete. Preparing to delete original folder: {project_path}")
        if not force:
            confirm = input(f"Are you sure you want to permanently delete {project_path}? [y/N]: ").strip().lower()
            if confirm != "y":
                print("🛑 Deletion cancelled.")
                return archive_path, sha256_path, readme_path

        try:
            shutil.rmtree(project_path)
            print(f"🗑️ Deleted original folder: {project_path}")
        except Exception as e:
            print(f"❌ Failed to delete folder: {e}")

    return archive_path, sha256_path, readme_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Archive a project folder with metadata and checksum for long-term storage.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Required arguments
    parser.add_argument("project_path", help="Path to the project directory to archive")
    parser.add_argument("archive_dir", help="Directory where the archive and metadata will be stored")

    # Basic options
    parser.add_argument("--note", help="Optional note or description for the archive", default=None)
    parser.add_argument("--no-archive", action="store_true", help="Skip creating the .tar.gz archive")
    parser.add_argument("--delete-after-archive", action="store_true", help="Delete original folder after archiving")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")

    # Compression options
    parser.add_argument("--compress-level", type=int, choices=range(1,10), default=6,
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
            args.project_path,
            archive_dir,
            note=args.note,
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
        print("\n⚠️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if os.environ.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)
