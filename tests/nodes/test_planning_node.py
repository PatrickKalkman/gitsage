"""Tests for the Analysis Planning Node."""

import pytest
import os
from pathlib import Path
from git import Repo

from datetime import datetime

from unittest.mock import patch

from gitsage.nodes.planning_node import planning_node
from gitsage.models.base import CommitInfo
from gitsage.models.analysis import AnalysisPlan
from gitsage.models.state import AgentState


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
    suggestion = (
        "Consider adding more details about the implementation, "
        "such as where the authentication was added (files, functions) "
        "and how it integrates with the existing system."
    )
    return {
        "message_clarity": 0.9,
        "needs_code_review": True,
        "suggested_improvements": [suggestion],
        "is_breaking_change": False,
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
async def test_planning_node_run(sample_repo, api_key, mock_message_analysis):
    """Test the complete planning node execution."""
    repo_path, commit_hashes = sample_repo

    with patch("langchain_core.runnables.base.RunnableSerializable.ainvoke") as mock_invoke:
        mock_invoke.return_value = mock_message_analysis

        # Create initial state
        initial_state: AgentState = {
            "groq_api_key": api_key,
            "repo_path": repo_path,
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
        result = await planning_node(initial_state)

        # Verify state updates
        assert "commit_clarity" in result
        assert len(result["commit_clarity"]) == len(commit_hashes)
        assert "commits_needing_review" in result
        assert "analysis_plan" in result

        # Check analysis plan structure using dataclass attributes
        plan: AnalysisPlan = result["analysis_plan"]
        assert "target_audiences" in plan
        assert "required_formats" in plan
        assert "focus_areas" in plan
        assert "additional_analysis_needed" in plan
        assert "risk_level" in plan

        # Validate analysis plan content
        assert isinstance(plan["target_audiences"], list)
        assert isinstance(plan["required_formats"], list)
        assert isinstance(plan["focus_areas"], list)
        assert isinstance(plan["additional_analysis_needed"], bool)
        assert plan["risk_level"] in ["high", "normal"]

        # Validate specific content expectations
        assert "developers" in plan["target_audiences"]
        assert "markdown" in plan["required_formats"]
        assert any(area in ["features", "code_changes"] for area in plan["focus_areas"])
