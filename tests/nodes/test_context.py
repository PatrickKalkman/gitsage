"""Tests for the Code Context Node implementation."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from git import Repo, Commit
from git.diff import Diff

from gitsage.types.state import AgentState
from gitsage.types.base import CommitInfo
from gitsage.nodes.context import (
    context_node,
    extract_file_changes,
    identify_api_changes,
    detect_dependency_updates,
    analyze_schema_changes,
)


@pytest.fixture
def mock_diff():
    """Create a mock Git diff object with proper encoding."""
    diff = Mock(spec=Diff)
    diff.a_path = "test_file.py"
    diff.b_path = "test_file.py"
    diff.new_file = False
    diff.deleted_file = False
    # Ensure diff content is properly encoded
    diff.diff = b"Sample diff content"
    return diff


@pytest.fixture
def mock_commit():
    """Create a mock Git commit object with NULL_TREE handling."""
    commit = Mock(spec=Commit)
    commit.hexsha = "abc123"
    commit.message = "test commit"
    # Handle the NULL_TREE case
    parent_commit = Mock(spec=Commit)
    commit.parents = [parent_commit]
    commit.diff = MagicMock(return_value=[])
    return commit


@pytest.fixture
def sample_state():
    """Create a sample AgentState with proper typing."""
    return AgentState(
        {
            "repo_path": "/test/repo",
            "commits": [
                CommitInfo(
                    hash="abc123",
                    message="test commit",
                    author="Test Author",
                    date=datetime.now(),
                    files_changed=["test_file.py"],
                )
            ],
            "errors": [],
        }
    )


def test_extract_file_changes(mock_commit, mock_diff):
    """Test extraction of file changes with proper path handling."""
    mock_diff.diff = b"+def new_function():\n    pass\n-def old_function():\n    pass"
    mock_commit.diff.return_value = [mock_diff]

    changes = extract_file_changes(mock_commit)

    assert isinstance(changes, dict)
    assert "modified_files" in changes
    assert "patches" in changes
    assert mock_diff.b_path in changes["patches"]
    assert ".py" in changes["file_types"]


@pytest.mark.parametrize(
    "file_content,expected_count,expected_breaking",
    [
        (
            b"+def new_api():\n    pass\n-def old_api():\n    pass",
            1,
            True,  # Breaking because there's a removal
        ),
        (
            b"+def add_new_endpoint():\n    pass",
            1,
            False,  # Non-breaking because it's only an addition
        ),
        (b"def unchanged_api():\n    pass", 0, False),
    ],
)
def test_identify_api_changes(file_content, expected_count, expected_breaking):
    """Test API change detection with breaking changes."""
    mock_diff = Mock(spec=Diff)
    mock_diff.diff = file_content
    mock_diff.a_path = "api/controller.py"
    mock_diff.b_path = "api/controller.py"

    changes = {"patches": {"api/controller.py": file_content.decode()}, "modified_files": {"api/controller.py"}}

    api_changes = identify_api_changes(changes)

    assert len(api_changes) == expected_count
    if expected_count > 0:
        assert api_changes[0].breaking == expected_breaking


@pytest.mark.parametrize(
    "file_name,content,expected_count,expected_version",
    [
        ("requirements.txt", "+requests==2.26.0\n-requests==2.25.0", 1, "2.26.0"),
        ("package.json", '+  "react": "17.0.2"', 1, "17.0.2"),
        ("go.mod", "+require github.com/pkg/errors v0.9.1", 1, "v0.9.1"),
    ],
)
def test_detect_dependency_updates(file_name, content, expected_count, expected_version):
    """Test dependency update detection with version checking."""
    changes = {"patches": {file_name: content}}

    updates = detect_dependency_updates(changes)
    assert len(updates) == expected_count
    if expected_count > 0:
        assert updates[0].new_version == expected_version


@pytest.mark.parametrize(
    "file_path,content,expected_count,expected_migration",
    [
        (
            "models/user.py",
            """
            class User:
                id: int
                name: str
            """,
            0,
            False,
        ),
        ("migrations/001_create_users.sql", "CREATE TABLE users (id INT, name TEXT);", 1, True),
        ("models/migration_20240104.sql", "DROP TABLE users;", 1, True),
    ],
)
def test_analyze_schema_changes(file_path, content, expected_count, expected_migration):
    """Test schema change detection with migration requirements."""
    changes = {"patches": {file_path: content}}

    schema_changes = analyze_schema_changes(changes)
    assert len(schema_changes) == expected_count
    if expected_count > 0:
        assert schema_changes[0].migration_required == expected_migration


@patch("gitsage.nodes.context.Repo")
def test_context_node_integration(mock_repo_class, sample_state):
    """Test complete integration with all components."""
    # Setup mock repository
    mock_repo = Mock(spec=Repo)
    mock_repo_class.return_value = mock_repo

    # Create mock commit with multiple types of changes
    mock_commit = Mock(spec=Commit)
    mock_commit.parents = [Mock(spec=Commit)]

    # Setup different types of changes
    api_diff = Mock(spec=Diff)
    api_diff.a_path = api_diff.b_path = "api/users.py"
    api_diff.new_file = False
    api_diff.deleted_file = False
    api_diff.diff = b"+def new_user_api():\n    pass\n-def old_user_api():\n    pass"

    dep_diff = Mock(spec=Diff)
    dep_diff.a_path = dep_diff.b_path = "requirements.txt"
    dep_diff.new_file = False
    dep_diff.deleted_file = False
    dep_diff.diff = b"+requests==2.26.0\n-requests==2.25.0"

    schema_diff = Mock(spec=Diff)
    schema_diff.a_path = schema_diff.b_path = "models/user.py"
    schema_diff.new_file = True
    schema_diff.deleted_file = False
    schema_diff.diff = b"class User:\n    id: int\n    name: str"

    mock_commit.diff.return_value = [api_diff, dep_diff, schema_diff]
    mock_repo.commit.return_value = mock_commit

    # Execute node
    result_state = context_node(sample_state)

    # Verify all aspects of the integration
    assert "code_context" in result_state
    assert result_state["code_context"].api_changes
    assert result_state["code_context"].dependency_updates
    assert set([".py", ".txt"]).issubset(set(result_state["affected_file_types"]))
    assert not result_state["errors"]
