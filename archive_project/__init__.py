"""Coldstore - Cold storage archiving utility for long-term preservation with metadata."""

__version__ = "0.1.0"

from .core.archiver import archive_project

__all__ = ["archive_project"]