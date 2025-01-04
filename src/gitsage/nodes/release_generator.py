"""Release note generation node with intelligent commit categorization."""

from dataclasses import dataclass
from typing import List, Dict, TypedDict
from datetime import datetime

from gitsage.types.base import CommitInfo
from gitsage.types.state import AgentState


@dataclass
class ReleaseSection:
    """Represents a section in the release notes."""

    title: str
    entries: List[str]
    importance: int = 0


@dataclass
class ReleaseNote:
    """Represents a complete set of release notes."""

    version: str
    date: datetime
    summary: str
    sections: Dict[str, ReleaseSection]
    breaking_changes: List[str]


class CategoryConfig(TypedDict):
    """Configuration for commit categories."""

    keywords: List[str]
    importance: int


# Define category configurations
COMMIT_CATEGORIES: Dict[str, CategoryConfig] = {
    "added": {"keywords": ["feat", "feature", "add"], "importance": 3},
    "changed": {"keywords": ["change", "update", "enhance"], "importance": 2},
    "deprecated": {"keywords": ["deprecate"], "importance": 2},
    "removed": {"keywords": ["remove", "delete"], "importance": 3},
    "fixed": {"keywords": ["fix", "bug", "patch"], "importance": 1},
    "security": {"keywords": ["security", "vuln", "cve"], "importance": 4},
}


def categorize_commit(commit_info: CommitInfo, categories: Dict[str, CategoryConfig] = COMMIT_CATEGORIES) -> str:
    """Categorize a commit based on its message and changed files."""
    if commit_info.message:
        message_lower = commit_info.message.lower()
    else:
        return ""

    # Check for security changes first (highest priority)
    if any(kw in message_lower for kw in categories["security"]["keywords"]):
        return "security"

    # Look for category keywords in commit message
    for category, details in categories.items():
        if any(kw in message_lower for kw in details["keywords"]):
            return category

    return "changed"


def detect_breaking_changes(commit_info: CommitInfo) -> bool:
    """Detect if a commit contains breaking changes."""
    message_lower = commit_info.message.lower()
    breaking_indicators = [
        "breaking change",
        "breaking-change",
        "breaks backward compatibility",
        "migration required",
    ]
    return any(indicator in message_lower for indicator in breaking_indicators)


def generate_section_entries(commits: List[CommitInfo], category: str) -> List[str]:
    """Generate formatted entries for a section."""
    entries = []
    for commit in commits:
        if categorize_commit(commit) == category:
            # Format the commit message as a bullet point
            message_lines = commit.message.strip().split("\n")
            main_message = message_lines[0]

            # Add commit hash reference
            entry = f"- {main_message} ({commit.hash[:8]})"

            # Add any additional details from commit message
            if len(message_lines) > 1:
                details = "\n".join(f"  {line.strip()}" for line in message_lines[1:] if line.strip())
                if details:
                    entry += f"\n{details}"

            entries.append(entry)
    return entries


def generate_release_summary(sections: Dict[str, ReleaseSection], breaking_changes: List[str]) -> str:
    """Generate a high-level summary of the release."""
    summary_parts = []

    if breaking_changes:
        summary_parts.append("⚠️ This release contains breaking changes.")

    # Add high-level statistics
    stats = []
    for category, section in sections.items():
        if section.entries:
            stats.append(f"{len(section.entries)} {category}")

    if stats:
        summary_parts.append(
            f"This release includes {', '.join(stats[:-1])} and {stats[-1]} changes"
            if len(stats) > 1
            else f"This release includes {stats[0]} changes."
        )

    return " ".join(summary_parts)


def release_generator_node(state: AgentState) -> AgentState:
    """Generate release notes from the commit information."""
    commits = state.get("commits", [])
    version = state.get("end_ref", "Unreleased")

    # Initialize sections
    sections = {
        category: ReleaseSection(
            title=category.capitalize(),
            entries=[],
            importance=details["importance"],
        )
        for category, details in COMMIT_CATEGORIES.items()
    }

    # Process commits and collect breaking changes
    breaking_changes = []
    for commit in commits:
        # Categorize and generate section content
        category = categorize_commit(commit)
        sections[category].entries.extend(generate_section_entries([commit], category))

        # Check for breaking changes
        if detect_breaking_changes(commit):
            hash_short = commit.hash[:8]
            message_first_line = commit.message.split("\n")[0]
            breaking_changes.append(f"- {message_first_line} ({hash_short})")

    # Create release notes structure
    release_notes = ReleaseNote(
        version=version,
        date=datetime.now(),
        summary=generate_release_summary(sections, breaking_changes),
        sections={k: v for k, v in sections.items() if v.entries},
        breaking_changes=breaking_changes,
    )

    # Update state
    return {
        **state,
        "release_notes": release_notes,
        "has_breaking_changes": bool(breaking_changes),
    }
