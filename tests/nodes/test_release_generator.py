"""Integration test for the release notes generator."""

import pytest
from pathlib import Path
from git import Repo
from textwrap import dedent

from gitsage.nodes.commit_discovery import load_discovery_node
from gitsage.nodes.release_generator import load_release_generator


def create_commit(repo: Repo, file_path: Path, content: str, message: str) -> None:
    """Helper function to create a commit in the test repository."""
    file_path.write_text(content)
    repo.index.add([str(file_path)])
    repo.index.commit(message)


@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample repository with various types of commits."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Create test files
    src_file = repo_path / "src" / "main.py"
    test_file = repo_path / "tests" / "test_main.py"
    docs_file = repo_path / "docs" / "README.md"

    # Create directories
    src_file.parent.mkdir(parents=True)
    test_file.parent.mkdir(parents=True)
    docs_file.parent.mkdir(parents=True)

    # Initial commit
    create_commit(repo, src_file, "print('Hello World')", "Initial commit")

    # Feature addition with breaking change
    create_commit(
        repo,
        src_file,
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
    )

    # Bug fix
    create_commit(
        repo,
        test_file,
        "def test_greet(): assert greet('World') == 'Hello World'",
        "fix: Correct greeting test case",
    )

    # Security update
    create_commit(
        repo,
        src_file,
        "import html; print(html.escape('Hello World'))",
        dedent("""security: Add HTML escaping

        - Prevents XSS attacks in output
        - Updates security policy
        """),
    )

    # Documentation update
    create_commit(
        repo,
        docs_file,
        "# Usage Guide\n\nSee examples below...",
        "docs: Add initial documentation",
    )

    # Deprecation notice
    create_commit(
        repo,
        src_file,
        dedent("""
        import warnings
        def old_greet(name):
            warnings.warn("Use greet() instead", DeprecationWarning)
            return f"Hello {name}"
        """),
        dedent("""deprecate: Mark old_greet as deprecated

        - Function will be removed in v2.0
        - Use new greet() function instead
        """),
    )

    return repo_path


def test_release_notes_generation(sample_repo):
    """Test the complete release notes generation process."""
    # Initialize nodes
    discovery_node = load_discovery_node(str(sample_repo))
    generator_node = load_release_generator()

    # Process commits
    state = discovery_node.run({})
    result = generator_node.run(state)

    # Get generated release notes
    release_notes = result["release_notes"]

    # Print the generated release notes for inspection
    print("\nGenerated Release Notes:")
    print("=" * 50)
    print(f"Version: {release_notes.version}")
    print(f"Date: {release_notes.date}")
    print("\nSummary:")
    print(release_notes.summary)

    if release_notes.breaking_changes:
        print("\nBreaking Changes:")
        for change in release_notes.breaking_changes:
            print(change)

    print("\nChanges by Category:")
    for section_name, section in release_notes.sections.items():
        if section.entries:
            print(f"\n{section.title}:")
            for entry in section.entries:
                print(entry)

    # Verify structure and content
    assert "security" in release_notes.sections
    assert "fixed" in release_notes.sections
    assert release_notes.breaking_changes
    assert any(
        "HTML escaping" in entry for entry in release_notes.sections["security"].entries
    )
    assert any(
        "formal greeting" in entry for entry in release_notes.sections["added"].entries
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
