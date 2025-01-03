"""Tests for the Analysis Planning Node."""

import pytest
import os
from pathlib import Path
from git import Repo

from datetime import datetime

from unittest.mock import patch

from gitsage.nodes.planning import load_planning_node, CommitClarity
from gitsage.types.base import CommitInfo


@pytest.fixture
def api_key():
    """Get Groq API key from environment."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        pytest.skip("GROQ_API_KEY not set in environment")
    return key


@pytest.fixture
def mock_message_analysis():
    """Mock response for commit message analysis."""
    return {
        "message_clarity": 0.9,
        "needs_code_review": True,
        "suggested_improvements": [
            "Consider adding more details about the implementation, such as where the authentication was added (files, functions) and how it integrates with the existing system."
        ],
        "is_breaking_change": False,
    }


@pytest.fixture
def mock_code_analysis():
    """Mock response for code change analysis."""
    return {
        "functional_changes": "Updated authentication logic",
        "impact_assessment": "Moderate impact on user sessions",
        "risk_factors": ["Session handling changes", "Database updates"],
        "technical_details": "Modified login flow and session management",
    }


def create_test_commit(repo: Repo, message: str, content: str) -> str:
    """Helper to create a test commit."""
    test_file = Path(repo.working_dir) / "test.py"
    test_file.write_text(content)
    repo.index.add([str(test_file)])
    commit = repo.index.commit(message)
    return commit.hexsha


@pytest.fixture
def sample_repo(tmp_path):
    """Create a repository with various commit types."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    commits = []

    # Clear, conventional commit
    commits.append(
        create_test_commit(
            repo,
            """feat: Add user authentication

        Implements OAuth2 authentication flow with:
        - Google sign-in support
        - JWT token handling
        - Session management

        No breaking changes.""",
            "def authenticate(): pass",
        )
    )

    # Unclear commit
    commits.append(create_test_commit(repo, "fixed auth stuff", "def auth(): return True"))

    # Breaking change
    commits.append(
        create_test_commit(
            repo,
            """refactor: Update API endpoints

        BREAKING CHANGE: Authentication endpoints now require API key
        - Modified response format
        - Updated error handling
        - Added rate limiting""",
            "class APIAuth: pass",
        )
    )

    return repo_path, commits


@pytest.mark.asyncio
async def test_commit_analysis(sample_repo, api_key, mock_message_analysis, mock_code_analysis):
    """Test commit message and code analysis."""
    repo_path, commit_hashes = sample_repo

    with patch("langchain_core.runnables.base.RunnableSerializable.ainvoke") as mock_invoke:
        mock_invoke.side_effect = [mock_message_analysis, mock_code_analysis] * len(commit_hashes)

        node = load_planning_node(api_key)
        repo = Repo(repo_path)

        commit = repo.commit(commit_hashes[0])
        clarity = await node.analyze_commit(repo, commit)

        # Basic type and property checks
        assert isinstance(clarity, CommitClarity)
        assert clarity.commit_hash == commit_hashes[0]
        assert clarity.message_clarity == mock_message_analysis["message_clarity"]
        assert clarity.needs_code_review == mock_message_analysis["needs_code_review"]

        # Check if the suggestion starts with the expected phrase
        assert any(
            suggestion.startswith("Consider adding more details") for suggestion in clarity.suggested_improvements
        )


@pytest.mark.asyncio
async def test_planning_node_run(sample_repo, api_key, mock_message_analysis):
    """Test the complete planning node execution."""
    repo_path, commit_hashes = sample_repo

    with patch("langchain_core.runnables.base.RunnableSerializable.ainvoke") as mock_invoke:
        mock_invoke.return_value = mock_message_analysis

        node = load_planning_node(api_key)

        # Create initial state
        initial_state = {
            "repository_path": repo_path,
            "commits": [
                CommitInfo(
                    hash=commit_hash,
                    message="Test commit",
                    author="Test Author",
                    date=datetime.now(),
                    files_changed=["test.py"],
                )
                for commit_hash in commit_hashes
            ],
        }

        # Run planning node
        result = await node.run(initial_state)

        # Verify state updates
        assert "commit_clarity" in result
        assert len(result["commit_clarity"]) == len(commit_hashes)
        assert "commits_needing_review" in result
        assert "analysis_plan" in result

        # Check analysis plan structure
        plan = result["analysis_plan"]
        assert "target_audiences" in plan
        assert "required_formats" in plan
        assert "focus_areas" in plan
        assert "additional_analysis_needed" in plan
        assert "risk_level" in plan


@pytest.mark.asyncio
async def test_unclear_commit_handling(sample_repo, api_key):
    """Test handling of unclear commits with real API."""
    repo_path, commit_hashes = sample_repo

    # Only run this test if API key is available
    if not api_key:
        pytest.skip("GROQ_API_KEY not set")

    node = load_planning_node(api_key)
    repo = Repo(repo_path)

    # Analyze the unclear commit
    unclear_commit = repo.commit(commit_hashes[1])  # "fixed auth stuff"
    clarity = await node.analyze_commit(repo, unclear_commit)

    # Verify analysis results
    assert clarity.commit_hash == commit_hashes[1]
    assert clarity.needs_code_review  # Should need review due to unclear message
    assert clarity.message_clarity < 0.7  # Should have lower clarity score
    assert clarity.suggested_improvements  # Should suggest improvements
    assert clarity.code_changes_summary  # Should include code analysis


@pytest.mark.asyncio
async def test_breaking_change_detection(sample_repo, api_key, mock_message_analysis):
    """Test detection of breaking changes."""
    repo_path, commit_hashes = sample_repo

    with patch("langchain_core.runnables.base.RunnableSerializable.ainvoke") as mock_invoke:
        mock_invoke.return_value = {
            **mock_message_analysis,
            "is_breaking_change": True,
            "message_clarity": 0.9,
        }

        node = load_planning_node(api_key)
        repo = Repo(repo_path)

        breaking_commit = repo.commit(commit_hashes[2])
        result = await node.analyze_commit(repo, breaking_commit)

        # Changed to >= to include threshold value
        assert result.message_clarity >= 0.8  # Clear breaking change announcement
        assert result.needs_code_review  # Breaking changes should trigger review
