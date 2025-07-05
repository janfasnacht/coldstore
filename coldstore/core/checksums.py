"""Checksum calculation and verification for coldstore."""

import datetime
import hashlib
from pathlib import Path


def calculate_file_sha256(file_path: Path, show_progress: bool = True) -> str:
    """Calculate SHA256 checksum for a single file with optional progress."""
    sha256_hash = hashlib.sha256()
    total_size = file_path.stat().st_size
    bytes_read = 0
    last_progress = 0

    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
            bytes_read += len(byte_block)

            if show_progress and total_size > 0:
                progress = int(bytes_read / total_size * 100)
                if progress > last_progress and progress % 5 == 0:
                    print(f"    Progress: {progress}%", end="\r")
                    last_progress = progress

    return sha256_hash.hexdigest()


def calculate_checksums_for_parts(archive_paths: list[Path]) -> list[tuple[str, str]]:
    """Calculate SHA256 checksums for multiple archive parts.

    Returns:
        List of tuples (filename, sha256_hash)
    """
    print("🔐 Calculating SHA256 checksums...")
    sha256_hashes = []

    for i, part_path in enumerate(archive_paths):
        if len(archive_paths) > 1:
            print(f"  Part {i+1}/{len(archive_paths)}: {part_path.name}")

        sha256_hex = calculate_file_sha256(part_path)
        sha256_hashes.append((part_path.name, sha256_hex))
        print(f"\n    ✅ {part_path.name}: {sha256_hex}")

    return sha256_hashes


def write_sha256_file(
    sha256_path: Path,
    sha256_hashes: list[tuple[str, str]],
    is_split: bool = False
) -> str:
    """Write SHA256 file(s) and return master hash.

    Args:
        sha256_path: Path for SHA256 file
        sha256_hashes: List of (filename, hash) tuples
        is_split: Whether this is a split archive

    Returns:
        Master hash string
    """
    if len(sha256_hashes) == 1 and not is_split:
        # Single archive
        with open(sha256_path, "w") as f:
            f.write(f"{sha256_hashes[0][1]}  {sha256_hashes[0][0]}\n")
        master_hash = sha256_hashes[0][1]
    else:
        # Multiple archives - create master SHA256 file
        with open(sha256_path, "w") as f:
            f.write("# Split Archive SHA256 Checksums\n")
            f.write(f"# Created: {datetime.datetime.now()}\n")
            f.write(f"# Parts: {len(sha256_hashes)}\n\n")
            for filename, hash_val in sha256_hashes:
                f.write(f"{hash_val}  {filename}\n")

        # Calculate master hash from all part hashes
        master_sha256 = hashlib.sha256()
        for _, hash_val in sha256_hashes:
            master_sha256.update(hash_val.encode())
        master_hash = master_sha256.hexdigest()

    return master_hash
