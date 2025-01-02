"""
GitSage agent state models for managing discovery and analysis state.
"""

from typing import List, Optional, TypedDict
from datetime import datetime
from dataclasses import dataclass


@dataclass
class CommitInfo:
    """Structured representation of a Git commit."""

    hash: str
    message: str
    author: str
    date: datetime
    files_changed: List[str]


class AgentState(TypedDict, total=False):
    """State container for the GitSage agent.

    Using TypedDict for LangGraph compatibility. total=False means all fields
    are optional.
    """

    # Discovery state
    commits: List[CommitInfo]  # List of discovered commits
    commit_count: int  # Number of commits in the current range
    context: str  # Context describing the current commit range
    start_ref: Optional[str]  # Starting reference (tag/commit) for the commit range
    end_ref: str  # Ending reference (tag/commit) for the commit range
    last_tag: Optional[str]  # Most recent tag in the repository
    all_tags: List[str]  # All tags in the repository

    # Discovery configuration
    since_ref: Optional[str]  # Override to show commits since this reference
