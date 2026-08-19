"""
tsktui: Terminal User Interface for The Sleuth Kit (TSK) & Autopsy triage.
"""

__version__ = "0.1.0"
__author__ = "DFIR Community"
__license__ = "MIT"

from .backend import TSKBackend, Partition, FileEntry
from .ui import TSKTUIApp

__all__ = ["TSKTUIApp", "TSKBackend", "Partition", "FileEntry", "__version__"]
