"""Tests for the release notes generator functionality."""

from typing import List
import pytest
from datetime import datetime
from pathlib import Path
from git import Repo
from textwrap import dedent

from gitsage.nodes.release_generator import (
    categorize_commit,
    detect_breaking_changes,
    generate_section_entries,
    generate_release_summary,
    release_generator_node,
    ReleaseSection,
)
from gitsage.types.base import CommitInfo
from gitsage.nodes.commit_discovery import commit_discovery_node


def create_test_commit(repo: Repo, file_path: Path, content: str, message: str) -> None:
    """Create a commit in the test repository."""
    file_path.write_text(content)
    repo.index.add([str(file_path)])
    repo.index.commit(message)


@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample repository with various types of commits."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Create test directories and files
    src_file = repo_path / "src" / "main.py"
    test_file = repo_path / "tests" / "test_main.py"
    docs_file = repo_path / "docs" / "README.md"

    for file_path in [src_file, test_file, docs_file]:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create diverse commit history
    commits = [
        # Initial commit
        ("src/main.py", "print('Hello World')", "Initial commit"),
        # Feature with breaking change
        (
            "src/main.py",
            dedent("""
            def greet(name: str, formal: bool = False) -> str:
                '''Breaking change: Added formal parameter'''
                return f"Dear {name}" if formal else f"Hello {name}"
            """),
            dedent("""feat: Add formal greeting option

            BREAKING CHANGE: greet() now requires a formal parameter
            - Added formal parameter to control greeting style
            - Updates all existing call sites required
            """),
        ),
        # Bug fix
        (
            "tests/test_main.py",
            "def test_greet(): assert greet('World') == 'Hello World'",
            "fix: Correct greeting test case",
        ),
        # Security update
        (
            "src/main.py",
            "import html; print(html.escape('Hello World'))",
            dedent("""security: Add HTML escaping

         - Prevents XSS attacks in output
         - Updates security policy
         """),
        ),
        # Documentation
        ("docs/README.md", "# Usage Guide\n\nSee examples below...", "docs: Add initial documentation"),
    ]

    # Create all commits
    for file_name, content, message in commits:
        create_test_commit(repo, repo_path / file_name, content, message)

    return repo_path


@pytest.fixture
def commit_info_factory():
    """Factory fixture for creating CommitInfo instances."""

    def create_commit_info(
        message: str, hash: str = "abcd1234", author: str = "Test Author", files_changed: List[str] = None
    ) -> CommitInfo:
        return CommitInfo(
            hash=hash, message=message, author=author, date=datetime.now(), files_changed=files_changed or ["test.py"]
        )

    return create_commit_info


def test_categorize_commit(commit_info_factory):
    """Test commit categorization logic."""
    test_cases = [
        ("feat: Add new feature", "added"),
        ("fix: Resolve bug", "fixed"),
        ("security: Patch vulnerability", "security"),
        ("chore: Update deps", "changed"),
        ("breaking change: API update", "changed"),
    ]

    for message, expected_category in test_cases:
        commit = commit_info_factory(message)
        assert categorize_commit(commit) == expected_category


def test_detect_breaking_changes(commit_info_factory):
    """Test breaking change detection."""
    breaking_messages = [
        "feat: New API\n\nBREAKING CHANGE: Updated interface",
        "refactor: Modify core\n\nbreaks backward compatibility",
        "feat: Update\n\nMigration required for existing users",
    ]

    non_breaking_messages = [
        "feat: Add feature",
        "fix: Update logic\n\nMinor changes",
        "docs: Update readme",
    ]

    for message in breaking_messages:
        commit = commit_info_factory(message)
        assert detect_breaking_changes(commit)

    for message in non_breaking_messages:
        commit = commit_info_factory(message)
        assert not detect_breaking_changes(commit)


def test_generate_section_entries(commit_info_factory):
    """Test section entry generation."""
    commits = [
        commit_info_factory("feat: Add user authentication\n\n- Implements OAuth\n- Adds tests"),
        commit_info_factory("feat: Update UI components"),
    ]

    entries = generate_section_entries(commits, "added")

    assert len(entries) == 2
    assert any("Add user authentication" in entry for entry in entries)
    assert any("Implements OAuth" in entry for entry in entries)
    assert any("(abcd1234)" in entry for entry in entries)


def test_generate_release_summary():
    """Test release summary generation."""
    sections = {
        "added": ReleaseSection("Added", ["feat 1", "feat 2"], 3),
        "fixed": ReleaseSection("Fixed", ["fix 1"], 1),
        "security": ReleaseSection("Security", [], 4),
    }
    breaking_changes = ["Major API change"]

    summary = generate_release_summary(sections, breaking_changes)

    assert "breaking changes" in summary.lower()
    assert "2 added" in summary
    assert "1 fixed" in summary


def test_release_generator_node_integration(sample_repo):
    """Test the complete release generator node workflow."""
    # Initialize state with test repository data
    initial_state = {
        "repo_path": str(sample_repo),
        "commits": [],  # Will be populated by discovery node
        "end_ref": "v1.0.0",
    }

    # Run discovery node first to get commits
    state_with_commits = commit_discovery_node(initial_state)

    # Run release generator node
    result = release_generator_node(state_with_commits)

    # Verify release notes structure and content
    release_notes = result["release_notes"]

    # assert release_notes.version == "v1.0.0"
    assert isinstance(release_notes.date, datetime)
    assert release_notes.summary
    assert release_notes.breaking_changes

    # Verify sections
    assert "security" in release_notes.sections
    assert "fixed" in release_notes.sections
    assert "added" in release_notes.sections

    # Verify content
    security_entries = release_notes.sections["security"].entries
    assert any("HTML escaping" in entry for entry in security_entries)

    added_entries = release_notes.sections["added"].entries
    assert any("formal greeting" in entry.lower() for entry in added_entries)


def test_error_handling(commit_info_factory):
    """Test error handling in the release generator node."""
    # Create state with malformed commit messages
    problematic_commits = [
        commit_info_factory("asd"),  # Empty message
        commit_info_factory("topper"),  # None message
        commit_info_factory("fix: " + "x" * 1000),  # Very long message
    ]

    initial_state = {
        "commits": problematic_commits,
        "end_ref": "v1.0.0",
    }

    # Verify node handles errors gracefully
    result = release_generator_node(initial_state)

    assert "release_notes" in result
    assert isinstance(result["release_notes"].summary, str)
    assert isinstance(result["has_breaking_changes"], bool)
