"""File system scanner with exclusion processing for coldstore."""

import fnmatch
import os
import stat as stat_module
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Default VCS directories to exclude
DEFAULT_VCS_DIRS = {".git", ".hg", ".svn", ".bzr", "CVS"}


class FileScanner:
    """
    File system scanner that walks directory trees with exclusion support.

    Designed for memory efficiency using iterator pattern. Returns files
    in deterministic lexicographic order for reproducible archives.
    """

    def __init__(
        self,
        source_root: Path,
        exclude_patterns: Optional[list[str]] = None,
        exclude_vcs: bool = True,
        respect_gitignore: bool = False,
    ):
        """
        Initialize file scanner.

        Args:
            source_root: Root directory to scan
            exclude_patterns: Glob patterns to exclude (e.g., ["*.pyc", "__pycache__"])
            exclude_vcs: Whether to exclude VCS directories (default: True)
            respect_gitignore: Whether to respect .gitignore files (default: False)
        """
        self.source_root = Path(source_root).resolve()
        self.exclude_patterns = exclude_patterns or []
        self.exclude_vcs = exclude_vcs
        self.respect_gitignore = respect_gitignore

        # Load .gitignore patterns if requested
        self.gitignore_patterns: list[str] = []
        if self.respect_gitignore:
            self.gitignore_patterns = self._load_gitignore_patterns()

    def _load_gitignore_patterns(self) -> list[str]:
        """
        Load patterns from .gitignore file if it exists.

        Returns:
            List of gitignore patterns
        """
        gitignore_path = self.source_root / ".gitignore"
        if not gitignore_path.exists():
            return []

        patterns = []
        try:
            with open(gitignore_path) as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        patterns.append(line)
        except OSError:
            # Silently ignore read errors
            pass

        return patterns

    def _should_exclude(self, path: Path, is_dir: bool = False) -> bool:  # noqa: C901
        """
        Check if a path should be excluded based on exclusion rules.

        Args:
            path: Path to check (relative to source_root)
            is_dir: Whether the path is a directory

        Returns:
            True if path should be excluded
        """
        # Convert to relative path for matching
        try:
            rel_path = path.relative_to(self.source_root)
        except ValueError:
            # Path is not relative to source_root
            return True

        rel_path_str = str(rel_path)
        path_parts = rel_path.parts

        # Check VCS directory exclusion
        if is_dir and self.exclude_vcs:
            if path.name in DEFAULT_VCS_DIRS:
                return True
            # Also check if any parent is a VCS dir
            if any(part in DEFAULT_VCS_DIRS for part in path_parts):
                return True

        # Check user-provided exclusion patterns
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(rel_path_str, pattern):
                return True
            # Also check just the filename
            if fnmatch.fnmatch(path.name, pattern):
                return True

        # Check .gitignore patterns
        for pattern in self.gitignore_patterns:
            # Simple gitignore matching (basic implementation)
            # TODO: Implement full gitignore spec (negation, directory markers, etc.)
            if fnmatch.fnmatch(rel_path_str, pattern):
                return True
            if fnmatch.fnmatch(path.name, pattern):
                return True

        return False

    def scan(self) -> Iterator[Path]:
        """
        Scan the source directory and yield paths in deterministic order.

        Yields paths in lexicographic order for deterministic archives.

        Note: This implementation loads all paths into memory before yielding
        to ensure deterministic ordering. For very large projects (100k+ files),
        this uses more memory than a pure streaming approach, but guarantees
        reproducible archives. Future optimization: streaming with stable sort.

        Yields:
            Absolute Path objects for each file/directory
        """
        if not self.source_root.exists():
            raise FileNotFoundError(f"Source root does not exist: {self.source_root}")

        if not self.source_root.is_dir():
            msg = f"Source root is not a directory: {self.source_root}"
            raise NotADirectoryError(msg)

        # Collect all paths first for sorting
        # Trade-off: uses more memory but ensures determinism
        all_paths: list[tuple[Path, bool]] = []  # (path, is_dir)

        for root_str, dirs, files in os.walk(self.source_root, topdown=True):
            root = Path(root_str)

            # Filter directories in-place to prevent os.walk from descending
            # Sort for deterministic traversal
            dirs_to_keep = []
            for dirname in sorted(dirs):
                dir_path = root / dirname
                if not self._should_exclude(dir_path, is_dir=True):
                    dirs_to_keep.append(dirname)
                    all_paths.append((dir_path, True))

            # Modify dirs in-place to affect os.walk behavior
            dirs[:] = dirs_to_keep

            # Process files (also sorted)
            for filename in sorted(files):
                file_path = root / filename
                if not self._should_exclude(file_path, is_dir=False):
                    all_paths.append((file_path, False))

        # Sort all paths lexicographically by their relative path
        all_paths.sort(key=lambda x: str(x[0].relative_to(self.source_root)))

        # Yield paths
        for path, _ in all_paths:
            yield path

    def count_files(self) -> dict[str, int]:
        """
        Count files, directories, and symlinks without yielding paths.

        Useful for progress estimation and dry-run previews.

        Returns:
            Dictionary with counts: {files, dirs, symlinks, total}
        """
        counts = {"files": 0, "dirs": 0, "symlinks": 0, "total": 0}

        for path in self.scan():
            if path.is_symlink():
                counts["symlinks"] += 1
            elif path.is_dir():
                counts["dirs"] += 1
            elif path.is_file():
                counts["files"] += 1

            counts["total"] += 1

        return counts

    def estimate_size(self) -> int:
        """
        Estimate total size of files to be archived in bytes.

        Returns:
            Total size in bytes
        """
        total_size = 0

        for path in self.scan():
            if path.is_file() and not path.is_symlink():
                try:
                    total_size += path.stat().st_size
                except OSError:
                    # Skip files that can't be stat'd
                    pass

        return total_size

    def collect_file_metadata(self, path: Path) -> dict:
        """
        Collect file metadata for manifest generation.

        Collects all metadata needed for FileEntry in manifest schema,
        ready to be passed to FileEntry constructor (issue #12).

        Args:
            path: Absolute path to file/directory

        Returns:
            Dictionary with metadata compatible with FileEntry schema
        """
        from coldstore.core.manifest import FileType

        try:
            rel_path = path.relative_to(self.source_root)
        except ValueError:
            rel_path = path  # Fallback if not relative

        # Determine file type
        if path.is_symlink():
            file_type = FileType.SYMLINK
            link_target = str(path.readlink()) if path.exists() else None
        elif path.is_dir():
            file_type = FileType.DIR
            link_target = None
        elif path.is_file():
            file_type = FileType.FILE
            link_target = None
        else:
            file_type = FileType.OTHER
            link_target = None

        # Get file stats
        try:
            st = path.lstat()  # Use lstat to not follow symlinks
            size = st.st_size if file_type == FileType.FILE else None
            mode = oct(stat_module.S_IMODE(st.st_mode))
            mtime_utc = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
            uid = st.st_uid
            gid = st.st_gid
            is_executable = bool(st.st_mode & stat_module.S_IXUSR)
        except OSError:
            # Fallback for inaccessible files
            size = None
            mode = "0000"
            mtime_utc = datetime.now(timezone.utc).isoformat()
            uid = 0
            gid = 0
            is_executable = False

        # File extension
        ext = path.suffix.lstrip(".") if path.suffix else ""

        return {
            "path": str(rel_path),
            "type": file_type,
            "size": size,
            "mode": mode,
            "mtime_utc": mtime_utc,
            "link_target": link_target,
            # uid, gid, is_executable, ext are for FILELIST.csv.gz
            "_uid": uid,
            "_gid": gid,
            "_is_executable": is_executable,
            "_ext": ext,
        }


# Convenience function for quick scans
def scan_directory(
    source_root: Path,
    exclude_patterns: Optional[list[str]] = None,
    exclude_vcs: bool = True,
    respect_gitignore: bool = False,
) -> Iterator[Path]:
    """
    Convenience function to scan a directory with default settings.

    Args:
        source_root: Root directory to scan
        exclude_patterns: Glob patterns to exclude
        exclude_vcs: Whether to exclude VCS directories
        respect_gitignore: Whether to respect .gitignore files

    Returns:
        Iterator of Path objects
    """
    scanner = FileScanner(
        source_root=source_root,
        exclude_patterns=exclude_patterns,
        exclude_vcs=exclude_vcs,
        respect_gitignore=respect_gitignore,
    )
    return scanner.scan()
