"""Tests for the commit discovery node."""

import pytest
from git import Repo

from gitsage.nodes.discovery import load_discovery_node


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary Git repository with commits and tags for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Create initial commit
    test_file = repo_path / "test.txt"
    test_file.write_text("Initial content")
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")

    # Add a release tag
    repo.create_tag("v1.0.0")

    # Add another commit
    test_file.write_text("Updated content")
    repo.index.add(["test.txt"])
    repo.index.commit("Update content")

    return repo_path


def test_commit_discovery_with_tag(temp_git_repo):
    """Test commit discovery with release tags."""
    node = load_discovery_node(str(temp_git_repo))
    state = node.run({})

    # Should only include commits after v1.0.0
    assert state["commit_count"] == 1
    assert len(state["commits"]) == 1
    assert state["last_release_tag"] == "v1.0.0"

    commit = state["commits"][0]
    assert "test.txt" in commit.files_changed
    assert commit.message == "Update content"


def test_commit_discovery_without_tag(temp_git_repo):
    """Test commit discovery with explicit reference override."""
    node = load_discovery_node(str(temp_git_repo))
    state = node.run({"since_ref": None})  # Explicitly request all commits

    assert state["commit_count"] == 2  # Should include all commits
    assert len(state["commits"]) == 2
