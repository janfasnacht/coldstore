"""Coldstore - Cold storage archiving utility for long-term preservation."""

__version__ = "0.1.0"

from .core.archive import create_coldstore_archive

__all__ = ["create_coldstore_archive"]
