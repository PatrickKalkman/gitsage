"""
GitSage commit discovery node with intelligent commit boundary detection.

This module automatically determines the relevant commit range for release notes
based on the repository's current state and tag history.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime

from git import Repo, NULL_TREE, Tag
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
    """Node responsible for intelligently discovering relevant commits
    for release notes."""

    def __init__(self, repo_path: str):
        """Initialize the node with a repository path."""
        self.repo = Repo(repo_path)

    def _get_release_tags(self) -> List[Tag]:
        """Get all release tags sorted by version number (highest first).

        Since Git tags don't reliably store creation time, we'll sort by version number
        assuming semantic versioning (e.g., v1.1.0 > v1.0.0).
        """

        def version_key(tag: Tag) -> tuple:
            # Remove 'v' prefix if present and split into version components
            name = tag.name
            if name.startswith("v"):
                name = name[1:]
            try:
                # Split version into numeric components
                parts = [int(x) for x in name.split(".")]
                # Pad with zeros if needed to ensure consistent comparison
                return tuple(parts + [0] * (3 - len(parts)))
            except (ValueError, AttributeError):
                # If tag doesn't follow version format, put it at the end
                return (-1, -1, -1)

        # Sort tags by version number
        tags = sorted(self.repo.tags, key=version_key, reverse=True)

        return tags

    def _get_commit_range(self) -> Tuple[Optional[str], str]:
        """Automatically determine the appropriate commit range for release notes.

        The logic is:
        1. If no tags exist, include all commits.
        2. If HEAD != latest_tag.commit, show changes since latest_tag.
        3. Otherwise (HEAD == latest_tag.commit):
           - If at least two tags exist, show changes between the two latest tags.
           - Else (only one tag), just show everything up to that single tag.
        """
        tags = self._get_release_tags()
        if not tags:
            return None, "HEAD"

        latest_tag = tags[0]

        # If HEAD points to the same commit as the latest tag, there are no new commits
        if self.repo.head.commit == latest_tag.commit:
            if len(tags) >= 2:
                previous_tag = tags[1]
                return previous_tag.name, latest_tag.name
            else:
                # Only one tag exists, and HEAD == that tag
                return None, latest_tag.name
        else:
            # HEAD has moved on since the latest tag => unreleased changes exist
            return latest_tag.name, "HEAD"

    def _get_commits(self, start_ref: Optional[str], end_ref: str) -> List[CommitInfo]:
        """Retrieve commits in the specified range."""
        try:
            if start_ref:
                rev_range = f"{start_ref}..{end_ref}"
                commits = list(self.repo.iter_commits(rev_range))
            else:
                commits = list(self.repo.iter_commits(end_ref))
            return [CommitInfo.from_git_commit(commit) for commit in commits]
        except Exception as e:
            print(f"Error retrieving commits: {str(e)}")
            return []

    def run(self, state: Dict) -> Dict:
        """Execute the commit discovery process.

        Args:
            state: The current agent state. If 'since_ref' is provided, it
            overrides automatic range detection.

        Returns:
            Updated state containing discovered commits and context.
        """
        tags = self._get_release_tags()

        # Allow explicit override
        if "since_ref" in state:
            start_ref = state["since_ref"]
            end_ref = "HEAD"
        else:
            # Automatically determine the range
            start_ref, end_ref = self._get_commit_range()

        commits = self._get_commits(start_ref, end_ref)

        # Determine context
        if "since_ref" in state:
            context = f"commits since {start_ref}"
        else:
            if not tags:
                context = "initial release - showing all commits"
            elif end_ref == "HEAD":
                context = "unreleased changes since last tag"
            else:
                context = "changes in last release"

        current_tags = self._get_release_tags()

        return {
            **state,
            "commits": commits,
            "commit_count": len(commits),
            "context": context,
            "start_ref": start_ref,
            "end_ref": end_ref,
            "last_tag": current_tags[0].name if current_tags else None,
            "all_tags": [tag.name for tag in current_tags],
        }


def load_discovery_node(repo_path: str) -> CommitDiscoveryNode:
    """Factory function to create a configured CommitDiscoveryNode."""
    return CommitDiscoveryNode(repo_path)
