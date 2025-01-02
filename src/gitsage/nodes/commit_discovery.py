"""
GitSage commit discovery node with intelligent commit boundary detection.
"""

from typing import List, Optional, Tuple
from git import Repo, NULL_TREE, Tag
from git.objects.commit import Commit
from datetime import datetime

from gitsage.types.state import AgentState, CommitInfo


class CommitDiscoveryNode:
    """Node responsible for intelligently discovering relevant commits
    for release notes."""

    def __init__(self, repo_path: str):
        """Initialize the node with a repository path."""
        self.repo = Repo(repo_path)

    def _get_release_tags(self) -> List[Tag]:
        """Get all release tags sorted by version number (highest first)."""

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

        return sorted(self.repo.tags, key=version_key, reverse=True)

    def _create_commit_info(self, commit: Commit) -> CommitInfo:
        """Create a CommitInfo instance from a GitPython Commit object."""
        parent = commit.parents[0] if commit.parents else NULL_TREE
        diff_index = commit.diff(parent)
        files_changed = []

        for diff in diff_index:
            if diff.a_path:
                files_changed.append(diff.a_path)
            if diff.b_path and diff.b_path != diff.a_path:
                files_changed.append(diff.b_path)

        return CommitInfo(
            hash=commit.hexsha,
            message=commit.message.strip(),
            author=commit.author.name,
            date=datetime.fromtimestamp(commit.authored_date),
            files_changed=files_changed,
        )

    def _get_commit_range(self) -> Tuple[Optional[str], str]:
        """Automatically determine the appropriate commit range for release notes."""
        tags = self._get_release_tags()

        if not tags:
            return None, "HEAD"  # Get all commits

        latest_tag = tags[0]
        head_commit = self.repo.head.commit
        latest_tag_commit = latest_tag.commit

        # Check if HEAD is at the latest tag
        if head_commit == latest_tag_commit:
            if len(tags) >= 2:
                # Show changes in the last release
                previous_tag = tags[1]
                return previous_tag.name, latest_tag.name
            else:
                # Only one tag exists and we're at it
                return None, latest_tag.name
        else:
            # There are new changes since the last tag
            return latest_tag.name, "HEAD"

    def _get_commits(self, start_ref: Optional[str], end_ref: str) -> List[CommitInfo]:
        """Retrieve commits in the specified range."""
        try:
            if start_ref:
                rev_range = f"{start_ref}..{end_ref}"
                commits = list(self.repo.iter_commits(rev_range))
            else:
                commits = list(self.repo.iter_commits(end_ref))

            return [self._create_commit_info(commit) for commit in commits]
        except Exception as e:
            print(f"Error retrieving commits: {str(e)}")
            return []

    def run(self, state: AgentState) -> AgentState:
        """Execute the commit discovery process."""
        # Handle explicit reference override
        if "since_ref" in state:
            start_ref = state["since_ref"]
            end_ref = "HEAD"
            context = f"commits since {start_ref}"
        else:
            # Automatically determine the appropriate range
            start_ref, end_ref = self._get_commit_range()

            # Determine context based on the range
            tags = self._get_release_tags()
            if not tags:
                context = "initial release - showing all commits"
            elif end_ref == "HEAD":
                context = "unreleased changes since last tag"
            else:
                context = "changes in last release"

        commits = self._get_commits(start_ref, end_ref)
        tags = self._get_release_tags()

        # Create new state with updates
        new_state: AgentState = {
            **state,
            "commits": commits,
            "commit_count": len(commits),
            "context": context,
            "start_ref": start_ref,
            "end_ref": end_ref,
            "last_tag": tags[0].name if tags else None,
            "all_tags": [tag.name for tag in tags],
        }

        return new_state


def load_discovery_node(repo_path: str) -> CommitDiscoveryNode:
    """Factory function to create a configured CommitDiscoveryNode."""
    return CommitDiscoveryNode(repo_path)
