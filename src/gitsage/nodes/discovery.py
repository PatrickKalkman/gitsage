"""
GitSage commit discovery node.

This module handles the retrieval and initial processing of Git commits,
using Git tags to determine release boundaries.
"""

from typing import Dict, List, Optional
from datetime import datetime

from git import Repo, NULL_TREE
from git.objects.commit import Commit
from pydantic import BaseModel, Field


class CommitInfo(BaseModel):
    """Structured representation of a Git commit."""

    hash: str = Field(..., description="The commit hash")
    message: str = Field(..., description="The commit message")
    author: str = Field(..., description="The commit author's name")
    date: datetime = Field(..., description="The commit timestamp")
    files_changed: List[str] = Field(
        default_factory=list, description="Files modified in this commit"
    )

    @classmethod
    def from_git_commit(cls, commit: Commit) -> "CommitInfo":
        """Create a CommitInfo instance from a GitPython Commit object."""
        parent = commit.parents[0] if commit.parents else NULL_TREE
        files_changed = [item.a_path or item.b_path for item in commit.diff(parent)]

        return cls(
            hash=commit.hexsha,
            message=commit.message.strip(),
            author=commit.author.name,
            date=datetime.fromtimestamp(commit.authored_date),
            files_changed=files_changed,
        )


class CommitDiscoveryNode:
    """Node responsible for discovering and retrieving Git commits since
    the latest release tag."""

    def __init__(self, repo_path: str):
        """Initialize the node with a repository path."""
        self.repo = Repo(repo_path)

    def _get_latest_release_tag(self) -> Optional[str]:
        """Find the most recent release tag by commit date."""
        tags = sorted(
            self.repo.tags, key=lambda t: t.commit.committed_date, reverse=True
        )
        return tags[0].name if tags else None

    def _get_commits_since(self, since_ref: Optional[str] = None) -> List[CommitInfo]:
        """Retrieve commits since the specified reference or all commits
        if no reference."""
        try:
            if since_ref:
                print(f"We are here: {since_ref}")
                # Get commits between the reference and HEAD
                commits = list(self.repo.iter_commits(f"{since_ref}..HEAD"))
            else:
                # Get all commits when no reference is provided
                commits = list(self.repo.iter_commits())
                print(f"Retrieved {len(commits)} commits")
            return [CommitInfo.from_git_commit(commit) for commit in commits]
        except Exception as e:
            # Log the error and return an empty list to maintain operation
            print(f"Error retrieving commits: {str(e)}")
            return []

    def run(self, state: Dict) -> Dict:
        """
        Execute the commit discovery process.

        Args:
            state: The current agent state. If 'since_ref' is provided, it will
                  override tag-based release detection. If explicitly None,
                  retrieves all commits.

        Returns:
            Updated state containing discovered commits and release information.
        """
        # Check if since_ref is explicitly set in state
        if "since_ref" in state:
            since_ref = state["since_ref"]  # Use the explicit value, even if None
        else:
            since_ref = self._get_latest_release_tag()

        commits = self._get_commits_since(since_ref)

        return {
            **state,
            "commits": commits,
            "commit_count": len(commits),
            "last_release_tag": since_ref,
        }


def load_discovery_node(repo_path: str) -> CommitDiscoveryNode:
    """Factory function to create a configured CommitDiscoveryNode."""
    return CommitDiscoveryNode(repo_path)
