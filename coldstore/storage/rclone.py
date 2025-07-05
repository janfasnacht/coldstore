"""Rclone storage backend for coldstore."""

import subprocess
from pathlib import Path
from typing import Any, Callable, Optional


def upload_files(
    files: list[Path],
    destination: str,
    storage_provider: str = "rclone",
    progress_callback: Optional[Callable[[Path, bool], None]] = None,
) -> dict[Path, dict[str, Any]]:
    """Generic file upload function supporting multiple cloud storage providers.

    Args:
        files: List of file paths to upload
        destination: Destination path/URL
        storage_provider: Which tool/method to use (currently only "rclone")
        progress_callback: Optional callback function for progress updates

    Returns:
        Dictionary mapping file paths to upload results
    """
    results = {}

    for f in files:
        if not f or not f.exists():
            continue

        print(f"Uploading {f}...")

        if storage_provider == "rclone":
            cmd = ["rclone", "copy", str(f), destination, "--progress"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                success = result.returncode == 0
                results[f] = {
                    "success": success,
                    "error": result.stderr if not success else None,
                }
                if not success:
                    print(f"❌ Error uploading {f.name}: {result.stderr}")
                else:
                    print(f"✅ Uploaded: {f.name}")
            except Exception as e:
                results[f] = {"success": False, "error": str(e)}
                print(f"❌ Exception during upload of {f.name}: {e}")
        else:
            # No other providers implemented yet
            results[f] = {"success": False, "error": "Provider not supported"}
            print(f"❌ Provider not supported: {storage_provider}")

        # Call progress callback if provided
        if progress_callback:
            progress_callback(f, results[f]["success"])

    return results
