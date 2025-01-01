"""
GitSage commit discovery node.

This module handles the retrieval and initial processing of Git commits,
preparing them for analysis by subsequent nodes in the pipeline.
"""

from typing import Dict, List
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
        # For the initial commit, diff against an empty tree
        parent = commit.parents[0] if commit.parents else NULL_TREE

        # Get the diff and extract changed files
        files_changed = [item.a_path or item.b_path for item in commit.diff(parent)]

        return cls(
            hash=commit.hexsha,
            message=commit.message.strip(),  # Strip trailing newlines
            author=commit.author.name,
            date=datetime.fromtimestamp(commit.authored_date),
            files_changed=files_changed,
        )


class CommitDiscoveryNode:
    """Node responsible for discovering and retrieving Git commits."""

    def __init__(self, repo_path: str):
        """Initialize the node with a repository path."""
        self.repo = Repo(repo_path)

    def _get_commits_since(self, since_ref: str | None = None) -> List[CommitInfo]:
        """Retrieve commits since the specified reference."""
        if since_ref:
            commits = list(self.repo.iter_commits(f"{since_ref}..HEAD"))
        else:
            commits = list(self.repo.iter_commits())

        return [CommitInfo.from_git_commit(commit) for commit in commits]

    def run(self, state: Dict) -> Dict:
        """
        Execute the commit discovery process.

        Args:
            state: The current agent state, may contain 'since_ref' to specify
                  commit range.

        Returns:
            Updated state with discovered commits.
        """
        since_ref = state.get("since_ref")
        commits = self._get_commits_since(since_ref)

        return {**state, "commits": commits, "commit_count": len(commits)}


def load_discovery_node(repo_path: str) -> CommitDiscoveryNode:
    """Factory function to create a configured CommitDiscoveryNode."""
    return CommitDiscoveryNode(repo_path)
