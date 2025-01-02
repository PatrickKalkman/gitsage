"""Base types used across the GitSage system."""

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class CommitInfo:
    """Information about a single commit."""

    hash: str
    message: str
    author: str
    date: datetime
    files_changed: List[str]
