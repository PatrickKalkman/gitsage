"""
Example program demonstrating GitSage release notes generation.
"""

import argparse
from pathlib import Path

from gitsage.nodes.commit_discovery_node import load_discovery_node
from gitsage.nodes.release_notes_renderer_node import load_release_generator


def format_release_notes(release_notes) -> str:
    """Format release notes into a markdown document."""
    output = []

    # Header
    output.append(f"# Release Notes - {release_notes.version}")
    output.append(f"Release Date: {release_notes.date.strftime('%B %d, %Y')}\n")

    # Summary
    output.append("## Summary")
    output.append(f"{release_notes.summary}\n")

    # Breaking Changes
    if release_notes.breaking_changes:
        output.append("## Breaking Changes")
        output.extend(release_notes.breaking_changes)
        output.append("")

    # Changes by Category
    for section_name, section in release_notes.sections.items():
        if section.entries:
            output.append(f"## {section.title}")
            output.extend(section.entries)
            output.append("")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Generate release notes for a Git repository")
    parser.add_argument("repo_path", help="Path to the Git repository")
    parser.add_argument("--output", "-o", help="Output file path (default: release_notes.md)")
    parser.add_argument("--since", help="Generate notes since this Git reference")
    args = parser.parse_args()

    # Validate repository path
    repo_path = Path(args.repo_path)
    if not (repo_path / ".git").exists():
        print(f"Error: {repo_path} is not a Git repository")
        return 1

    # Initialize nodes
    discovery_node = load_discovery_node(str(repo_path))
    generator_node = load_release_generator()

    # Prepare initial state
    initial_state = {}
    if args.since:
        initial_state["since_ref"] = args.since

    try:
        # Process commits
        print("Discovering commits...")
        state = discovery_node.run(initial_state)

        print(f"Found {state['commit_count']} commits")

        # Generate release notes
        print("Generating release notes...")
        state = generator_node.run(state)

        # Format output
        output = format_release_notes(state["release_notes"])

        # Write to file
        output_path = args.output or "release_notes.md"
        Path(output_path).write_text(output)
        print(f"\nRelease notes written to: {output_path}")

        return 0

    except Exception as e:
        print(f"Error generating release notes: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())
