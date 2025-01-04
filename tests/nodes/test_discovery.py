"""Tests for the commit discovery node."""

import pytest
from git import Repo
from pathlib import Path

from gitsage.nodes.commit_discovery import commit_discovery_node
from gitsage.types.state import AgentState


def create_commit(repo: Repo, file_path: Path, content: str, message: str) -> None:
    """Helper function to create a commit in the test repository."""
    file_path.write_text(content)
    repo.index.add([str(file_path.relative_to(file_path.parent))])
    return repo.index.commit(message)


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a basic temporary Git repository."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    return Repo.init(repo_path)


@pytest.fixture
def initial_repo(temp_git_repo):
    """Scenario 1: Repository with just commits, no tags yet."""
    repo = temp_git_repo
    repo_path = Path(repo.working_dir)

    # Create multiple commits
    test_file = repo_path / "test.txt"
    create_commit(repo, test_file, "Initial content", "Initial commit")
    create_commit(repo, test_file, "Feature A", "Add feature A")
    create_commit(repo, test_file, "Feature B", "Add feature B")

    return repo_path


@pytest.fixture
def single_tag_repo(temp_git_repo):
    """Scenario 2: Repository with one tag and unreleased changes."""
    repo = temp_git_repo
    repo_path = Path(repo.working_dir)
    test_file = repo_path / "test.txt"

    # Create initial commits and tag
    create_commit(repo, test_file, "Initial content", "Initial commit")
    create_commit(repo, test_file, "Feature A", "Add feature A")
    repo.create_tag("v1.0.0")

    # Add unreleased changes
    create_commit(repo, test_file, "Feature B", "Add feature B")
    create_commit(repo, test_file, "Feature C", "Add feature C")

    return repo_path


@pytest.fixture
def multi_tag_repo(temp_git_repo):
    """Scenario 3: Repository with multiple tags, no unreleased changes."""
    repo = temp_git_repo
    repo_path = Path(repo.working_dir)
    test_file = repo_path / "test.txt"

    # First release
    create_commit(repo, test_file, "Initial content", "Initial commit")
    create_commit(repo, test_file, "Feature A", "Add feature A")
    repo.create_tag("v1.0.0")

    # Second release
    create_commit(repo, test_file, "Feature B", "Add feature B")
    create_commit(repo, test_file, "Feature C", "Add feature C")
    repo.create_tag("v1.1.0")

    return repo_path


@pytest.fixture
def multi_tag_unreleased_repo(temp_git_repo):
    """Scenario 4: Repository with multiple tags and unreleased changes."""
    repo = temp_git_repo
    repo_path = Path(repo.working_dir)
    test_file = repo_path / "test.txt"

    # First release
    create_commit(repo, test_file, "Initial content", "Initial commit")
    repo.create_tag("v1.0.0")

    # Second release
    create_commit(repo, test_file, "Feature A", "Add feature A")
    repo.create_tag("v1.1.0")

    # Unreleased changes
    create_commit(repo, test_file, "Feature B", "Add feature B")
    create_commit(repo, test_file, "Feature C", "Add feature C")

    return repo_path


def test_initial_repo_discovery(initial_repo):
    """Test Scenario 1: Repository with no tags."""

    state = commit_discovery_node(AgentState(repo_path=str(initial_repo)))

    print(f"State: {state}")  # Print the state to see what it looks like

    assert state["commit_count"] == 3
    assert state["context"] == "initial release - showing all commits"
    assert state["start_ref"] is None
    assert state["end_ref"] == "HEAD"
    assert state["last_tag"] is None
    assert state["all_tags"] == []

    # Verify all commits are included
    messages = [c.message.strip() for c in state["commits"]]
    assert "Add feature B" in messages
    assert "Add feature A" in messages
    assert "Initial commit" in messages


def test_single_tag_with_unreleased(single_tag_repo):
    """Test Scenario 2: Repository with one tag and unreleased changes."""
    state = commit_discovery_node(AgentState(repo_path=str(single_tag_repo)))

    assert state["commit_count"] == 2  # Two commits after v1.0.0
    assert state["context"] == "unreleased changes since last tag"
    assert state["start_ref"] == "v1.0.0"
    assert state["end_ref"] == "HEAD"
    assert state["last_tag"] == "v1.0.0"

    # Verify only unreleased commits are included
    messages = [c.message.strip() for c in state["commits"]]
    assert "Add feature C" in messages
    assert "Add feature B" in messages
    assert "Add feature A" not in messages
    assert "Initial commit" not in messages


def test_multi_tag_no_unreleased(multi_tag_repo):
    """Test Scenario 3: Repository with multiple tags, no unreleased changes."""
    state = commit_discovery_node(AgentState(repo_path=str(multi_tag_repo)))

    assert state["commit_count"] == 2  # Commits between v1.0.0 and v1.1.0
    assert state["context"] == "changes in last release"
    assert state["start_ref"] == "v1.0.0"
    assert state["end_ref"] == "v1.1.0"
    assert state["last_tag"] == "v1.1.0"

    # Verify only commits between tags are included
    messages = [c.message.strip() for c in state["commits"]]
    assert "Add feature C" in messages
    assert "Add feature B" in messages
    assert "Add feature A" not in messages
    assert "Initial commit" not in messages


def test_multi_tag_with_unreleased(multi_tag_unreleased_repo):
    """Test Scenario 4: Repository with multiple tags and unreleased changes."""
    state = commit_discovery_node(AgentState(repo_path=str(multi_tag_unreleased_repo)))

    # In this case, we have 3 commits: the two after v1.1.0 and the v1.1.0 commit itself
    assert state["commit_count"] == 2  # Only commits after v1.1.0
    assert state["context"] == "unreleased changes since last tag"
    assert state["start_ref"] == "v1.1.0"
    assert state["end_ref"] == "HEAD"
    assert state["last_tag"] == "v1.1.0"

    # Verify only unreleased commits are included
    messages = [c.message.strip() for c in state["commits"]]
    assert "Add feature C" in messages
    assert "Add feature B" in messages
    assert "Add feature A" not in messages
    assert "Initial commit" not in messages


def test_explicit_reference_override(multi_tag_unreleased_repo):
    """Test explicit reference override using since_ref."""
    state = commit_discovery_node(AgentState(repo_path=str(multi_tag_unreleased_repo)))

    assert state["commit_count"] == 2  # Commits after v1.0.0
    assert state["start_ref"] == "v1.1.0"
    assert state["end_ref"] == "HEAD"
    assert state["context"] == "unreleased changes since last tag"

    # Verify all commits since v1.0.0 are included
    messages = [c.message.strip() for c in state["commits"]]
    assert "Add feature C" in messages
    assert "Initial commit" not in messages
