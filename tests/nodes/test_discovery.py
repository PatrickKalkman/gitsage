"""Tests for the commit discovery node."""

import pytest
from git import Repo

from gitsage.nodes.discovery import load_discovery_node


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary Git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Create an initial commit
    test_file = repo_path / "test.txt"
    test_file.write_text("Initial content")
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")

    return repo_path


def test_commit_discovery(temp_git_repo):
    """Test basic commit discovery functionality."""
    node = load_discovery_node(str(temp_git_repo))
    state = node.run({})

    assert state["commit_count"] == 1
    assert len(state["commits"]) == 1

    commit = state["commits"][0]
    assert commit.message == "Initial commit"
    assert "test.txt" in commit.files_changed
