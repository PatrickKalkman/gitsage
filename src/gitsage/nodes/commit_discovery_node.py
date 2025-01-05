"""
GitSage commit discovery node with intelligent commit boundary detection.
"""

from typing import List, Optional, Tuple
from git import Repo, NULL_TREE, Tag
from git.objects.commit import Commit
from datetime import datetime

from loguru import logger
from gitsage.models.state import AgentState, CommitInfo


def _get_release_tags(repo: Repo) -> List[Tag]:
    """Get all release tags sorted by version number (highest first)."""

    def version_key(tag: Tag) -> tuple:
        name = tag.name
        if name.startswith("v"):
            name = name[1:]
        try:
            parts = [int(x) for x in name.split(".")]
            return tuple(parts + [0] * (3 - len(parts)))
        except (ValueError, AttributeError):
            return (-1, -1, -1)

    return sorted(repo.tags, key=version_key, reverse=True)


def _create_commit_info(commit: Commit) -> CommitInfo:
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


def _get_commit_range(repo: Repo) -> Tuple[Optional[str], str]:
    """Automatically determine the appropriate commit range for release notes."""
    tags = _get_release_tags(repo)

    if not tags:
        return None, "HEAD"

    latest_tag = tags[0]
    head_commit = repo.head.commit
    latest_tag_commit = latest_tag.commit

    if head_commit == latest_tag_commit:
        if len(tags) >= 2:
            previous_tag = tags[1]
            return previous_tag.name, latest_tag.name
        else:
            return None, latest_tag.name
    else:
        return latest_tag.name, "HEAD"


def _get_commits(repo: Repo, start_ref: Optional[str], end_ref: str) -> List[CommitInfo]:
    """Retrieve commits in the specified range."""
    try:
        if start_ref:
            rev_range = f"{start_ref}..{end_ref}"
            commits = list(repo.iter_commits(rev_range))
        else:
            commits = list(repo.iter_commits(end_ref))

        return [_create_commit_info(commit) for commit in commits]
    except Exception as e:
        print(f"Error retrieving commits: {str(e)}")
        return []


def commit_discovery_node(state: AgentState) -> AgentState:
    """Process commits and update state with discovered information."""
    if "repo_path" not in state:
        raise ValueError("repo_path is required in AgentState")

    logger.info("Executing Commit Discovery Node")

    repo = Repo(state["repo_path"])
    if "since_ref" in state:
        start_ref = state["since_ref"]
        end_ref = "HEAD"
        context = f"commits since {start_ref}"
    else:
        # Automatically determine the appropriate range
        start_ref, end_ref = _get_commit_range(repo)

        # Determine context based on the range
        tags = _get_release_tags(repo)
        if not tags:
            context = "initial release - showing all commits"
        elif end_ref == "HEAD":
            context = "unreleased changes since last tag"
        else:
            context = "changes in last release"

    commits = _get_commits(repo, start_ref, end_ref)
    tags = _get_release_tags(repo)

    logger.info(f"Discovered {len(commits)} commits")

    # Update state with discoveries
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
