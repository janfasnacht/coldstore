"""Pytest configuration and shared fixtures for coldstore tests."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path_factory_fixture(tmp_path):
    """
    Provide a temporary directory for tests.

    This is a simple wrapper around pytest's tmp_path fixture
    for consistency with our testing approach.
    """
    return tmp_path


@pytest.fixture
def sample_files(tmp_path):
    """
    Create a sample file tree for testing.

    Creates a basic directory structure with various file types
    that can be used for scanner, archiver, and manifest tests.
    """
    # Create directory structure
    (tmp_path / "subdir1").mkdir()
    (tmp_path / "subdir2").mkdir()
    (tmp_path / ".git").mkdir()  # VCS directory

    # Create sample files
    (tmp_path / "file1.txt").write_text("Sample content 1\n")
    (tmp_path / "file2.py").write_text("# Python file\nprint('hello')\n")
    (tmp_path / "subdir1" / "nested.txt").write_text("Nested file\n")
    (tmp_path / "subdir2" / "data.csv").write_text("a,b,c\n1,2,3\n")
    (tmp_path / ".git" / "config").write_text("[core]\n")

    return tmp_path


@pytest.fixture
def mock_git_repo(tmp_path):
    """
    Create a mock git repository for testing git metadata collection.

    Note: This is a placeholder. Real git initialization will be added
    when implementing issue #16.
    """
    # TODO: Initialize actual git repo when implementing #16
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

    return tmp_path
