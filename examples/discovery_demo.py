#!/usr/bin/env python3
"""
examples/discovery_demo.py

Demonstrates the GitSage discovery node functionality by analyzing
the GitSage repository itself. This shows the first step of the
GitSage pipeline: commit discovery and analysis.
"""

import argparse
import os
import sys

from gitsage.nodes.discovery import load_discovery_node


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Demonstrate GitSage's commit discovery functionality"
    )
    parser.add_argument(
        "--repo-path",
        type=str,
        default=os.getcwd(),
        help="Path to Git repository (default: current directory)",
    )
    parser.add_argument(
        "--since-ref",
        type=str,
        help="Git reference to start from (default: latest release tag)",
    )
    return parser.parse_args()


def format_commit_info(commit) -> str:
    """Format a single commit's information for display.

    Args:
        commit: CommitInfo object containing commit details

    Returns:
        Formatted string containing commit information
    """
    files_changed_str = "\n  - ".join(
        [commit.files_changed[0]]  # First file
        + [f"{f}" for f in commit.files_changed[1:]]  # Remaining files
        if commit.files_changed
        else ["No files changed"]
    )

    return f"""
Commit: {commit.hash[:8]}
Author: {commit.author}
Date: {commit.date.strftime('%Y-%m-%d %H:%M:%S')}
Files Changed ({len(commit.files_changed)}):
  - {files_changed_str}
Message:
{commit.message}
{"=" * 80}
"""


def main():
    """Run the discovery node demo."""
    args = parse_args()
    repo_path = args.repo_path

    print(f"Running GitSage discovery node on repository: {repo_path}")
    print(f"Using reference: {args.since_ref or 'latest release tag'}")

    try:
        # Initialize the discovery node
        node = load_discovery_node(repo_path)

        # Run the node with optional since_ref
        initial_state = {}
        if args.since_ref is not None:
            initial_state["since_ref"] = args.since_ref

        state = node.run(initial_state)

        # Print summary
        print(f"\nDiscovered {state['commit_count']} commits")
        print(f"Last release tag: {state['last_release_tag']}")

        # Print detailed commit information
        print("\nDetailed commit information:")
        for commit in state["commits"]:
            print(format_commit_info(commit))

    except Exception as e:
        print(f"Error running discovery node: {str(e)}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
