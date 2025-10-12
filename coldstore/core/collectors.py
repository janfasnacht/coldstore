"""Metadata collectors for coldstore v2.0."""

import logging
import platform
import subprocess
import sys
from importlib.metadata import version as get_package_version
from pathlib import Path
from typing import Optional

from .manifest import (
    EnvironmentMetadata,
    GitMetadata,
    SystemMetadata,
    ToolsMetadata,
)

logger = logging.getLogger(__name__)


class GitMetadataCollector:
    """
    Collect git repository metadata.

    Detects git repository presence and collects commit, branch, tag,
    dirty status, and remote origin URL. Fails gracefully if git is
    not available or path is not a repository.
    """

    def __init__(self, source_path: Path):
        """
        Initialize git metadata collector.

        Args:
            source_path: Path to check for git repository
        """
        self.source_path = Path(source_path).resolve()

    def _run_git_command(
        self, args: list[str], check: bool = False
    ) -> Optional[str]:
        """
        Run git command and return output.

        Args:
            args: Git command arguments (e.g., ['status', '--porcelain'])
            check: Whether to raise exception on non-zero exit

        Returns:
            Command output stripped of whitespace, or None if command failed
        """
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.source_path,
                capture_output=True,
                text=True,
                check=check,
                timeout=5,  # Prevent hanging
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            return None

    def _is_git_available(self) -> bool:
        """Check if git command is available."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                timeout=2,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _is_git_repo(self) -> bool:
        """Check if source_path is inside a git repository."""
        result = self._run_git_command(["rev-parse", "--git-dir"])
        return result is not None

    def collect(self) -> GitMetadata:
        """
        Collect git metadata from source path.

        Returns:
            GitMetadata object with repository information
        """
        # Check if git is available
        if not self._is_git_available():
            logger.debug("Git not available")
            return GitMetadata(present=False)

        # Check if path is a git repository
        if not self._is_git_repo():
            logger.debug("Path is not a git repository: %s", self.source_path)
            return GitMetadata(present=False)

        # Collect git metadata
        commit = self._run_git_command(["rev-parse", "HEAD"])
        branch = self._run_git_command(["symbolic-ref", "--short", "HEAD"])

        # Try to get current tag (only if HEAD is exactly on a tag)
        tag = self._run_git_command(["describe", "--exact-match", "--tags", "HEAD"])

        # Check if working tree is dirty
        status_output = self._run_git_command(["status", "--porcelain"])
        dirty = bool(status_output) if status_output is not None else None

        # Get remote origin URL
        remote_origin_url = self._run_git_command(
            ["config", "--get", "remote.origin.url"]
        )

        return GitMetadata(
            present=True,
            commit=commit,
            branch=branch,
            tag=tag,
            dirty=dirty,
            remote_origin_url=remote_origin_url,
        )


class SystemMetadataCollector:
    """
    Collect system metadata (OS, hostname, architecture).

    Uses Python's platform module to gather system information.
    """

    def collect(self) -> SystemMetadata:
        """
        Collect system metadata.

        Returns:
            SystemMetadata object with OS, version, and hostname
        """
        try:
            os_name = platform.system()  # Darwin, Linux, Windows, etc.
            os_version = platform.release()  # e.g., 23.6.0, 5.15.0-97-generic
            hostname = platform.node()  # machine hostname

            return SystemMetadata(
                os=os_name,
                os_version=os_version,
                hostname=hostname,
            )
        except (OSError, RuntimeError) as e:
            # OSError: System-related errors (e.g., platform detection failures)
            # RuntimeError: Unexpected platform module errors
            logger.error("Failed to collect system metadata: %s", e)
            # Return fallback values
            return SystemMetadata(
                os="Unknown",
                os_version="Unknown",
                hostname="Unknown",
            )


class EnvironmentMetadataCollector:
    """
    Collect environment metadata (Python version, coldstore version, system info).

    Combines system metadata with tool versions.
    """

    def __init__(self, system_collector: Optional[SystemMetadataCollector] = None):
        """
        Initialize environment metadata collector.

        Args:
            system_collector: Optional SystemMetadataCollector instance
                (will create new one if not provided)
        """
        self.system_collector = system_collector or SystemMetadataCollector()

    def _get_python_version(self) -> str:
        """Get Python version string."""
        return (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )

    def _get_coldstore_version(self) -> str:
        """Get coldstore package version."""
        try:
            return get_package_version("coldstore")
        except Exception as e:
            logger.warning("Could not determine coldstore version: %s", e)
            return "unknown"

    def collect(self) -> EnvironmentMetadata:
        """
        Collect environment metadata.

        Returns:
            EnvironmentMetadata object with system and tools information
        """
        system = self.system_collector.collect()

        tools = ToolsMetadata(
            coldstore_version=self._get_coldstore_version(),
            python_version=self._get_python_version(),
        )

        return EnvironmentMetadata(system=system, tools=tools)


# Convenience functions for quick collection

def collect_git_metadata(source_path: Path) -> GitMetadata:
    """
    Convenience function to collect git metadata.

    Args:
        source_path: Path to check for git repository

    Returns:
        GitMetadata object
    """
    collector = GitMetadataCollector(source_path)
    return collector.collect()


def collect_system_metadata() -> SystemMetadata:
    """
    Convenience function to collect system metadata.

    Returns:
        SystemMetadata object
    """
    collector = SystemMetadataCollector()
    return collector.collect()


def collect_environment_metadata() -> EnvironmentMetadata:
    """
    Convenience function to collect environment metadata.

    Returns:
        EnvironmentMetadata object
    """
    collector = EnvironmentMetadataCollector()
    return collector.collect()
