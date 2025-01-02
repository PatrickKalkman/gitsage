from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

from gitsage.types.base import CommitInfo, AgentState


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


class ReleaseGeneratorNode:
    """Node responsible for generating structured release notes."""

    CATEGORIES = {
        "added": {"keywords": ["feat", "feature", "add"], "importance": 3},
        "changed": {"keywords": ["change", "update", "enhance"], "importance": 2},
        "deprecated": {"keywords": ["deprecate"], "importance": 2},
        "removed": {"keywords": ["remove", "delete"], "importance": 3},
        "fixed": {"keywords": ["fix", "bug", "patch"], "importance": 1},
        "security": {"keywords": ["security", "vuln", "cve"], "importance": 4},
    }

    def __init__(self, template_path: Optional[str] = None):
        """Initialize the release generator with optional custom template."""
        self.template_path = template_path

    def _categorize_commit(self, commit_info: CommitInfo) -> str:
        """Categorize a commit based on its message and changed files."""
        message_lower = commit_info.message.lower()

        # Check for security changes first (highest priority)
        if any(kw in message_lower for kw in self.CATEGORIES["security"]["keywords"]):
            return "security"

        # Look for category keywords in commit message
        for category, details in self.CATEGORIES.items():
            if any(kw in message_lower for kw in details["keywords"]):
                return category

        # Default to 'changed' if no specific category is found
        return "changed"

    def _detect_breaking_changes(self, commit_info: CommitInfo) -> bool:
        """Detect if a commit contains breaking changes."""
        message_lower = commit_info.message.lower()
        breaking_indicators = [
            "breaking change",
            "breaking-change",
            "breaks backward compatibility",
            "migration required",
        ]
        return any(indicator in message_lower for indicator in breaking_indicators)

    def _generate_section_content(
        self, commits: List[CommitInfo], category: str
    ) -> List[str]:
        """Generate formatted entries for a section."""
        entries = []
        for commit in commits:
            if self._categorize_commit(commit) == category:
                # Format the commit message as a bullet point
                message_lines = commit.message.strip().split("\n")
                main_message = message_lines[0]

                # Add commit hash reference
                entry = f"- {main_message} ({commit.hash[:8]})"

                # Add any additional details from commit message
                if len(message_lines) > 1:
                    details = "\n".join(
                        f"  {line.strip()}"
                        for line in message_lines[1:]
                        if line.strip()
                    )
                    if details:
                        entry += f"\n{details}"

                entries.append(entry)
        return entries

    def run(self, state: AgentState) -> AgentState:
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
            for category, details in self.CATEGORIES.items()
        }

        # Collect breaking changes
        breaking_changes = []

        # Process commits
        for commit in commits:
            category = self._categorize_commit(commit)
            sections[category].entries.extend(
                self._generate_section_content([commit], category)
            )

            if self._detect_breaking_changes(commit):
                hash_short = commit.hash[0:8]
                message_first_line = commit.message.split("\n")[0]
                breaking_changes.append(
                    "- {} ({})".format(message_first_line, hash_short)
                )

        # Create release notes structure
        release_notes = ReleaseNote(
            version=version,
            date=datetime.now(),
            summary=self._generate_summary(sections, breaking_changes),
            sections={k: v for k, v in sections.items() if v.entries},
            breaking_changes=breaking_changes,
        )

        # Update state
        new_state = {
            **state,
            "release_notes": release_notes,
            "has_breaking_changes": bool(breaking_changes),
        }

        return new_state

    def _generate_summary(
        self, sections: Dict[str, ReleaseSection], breaking_changes: List[str]
    ) -> str:
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
                f"This release includes {', '.join(stats[:-1])} and {stats[-1]} changes."
                if len(stats) > 1
                else f"This release includes {stats[0]} changes."
            )

        return " ".join(summary_parts)


def load_release_generator(template_path: Optional[str] = None) -> ReleaseGeneratorNode:
    """Factory function to create a configured ReleaseGeneratorNode."""
    return ReleaseGeneratorNode(template_path)
