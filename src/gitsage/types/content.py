"""Types for organizing and structuring release note content."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional


@dataclass
class ReleaseEntry:
    """A single entry in a release notes section."""

    content: str
    commit_hash: str
    author: str
    importance: int
    labels: List[str] = field(default_factory=list)
    related_issues: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReleaseSection:
    """A section in the release notes."""

    title: str
    entries: List[ReleaseEntry]
    description: Optional[str] = None
    importance: int = 0
    order: int = 0

    def add_entry(self, entry: ReleaseEntry) -> None:
        """Add an entry and maintain sorting by importance."""
        self.entries.append(entry)
        self.entries.sort(key=lambda x: (-x.importance, x.content))


@dataclass
class ReleaseStructure:
    """Organized structure of the release notes."""

    version: str
    date: datetime
    sections: Dict[str, ReleaseSection]
    summary: str
    contributors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_ordered_sections(self) -> List[ReleaseSection]:
        """Get sections ordered by importance and defined order."""
        return sorted(
            self.sections.values(), key=lambda x: (-x.importance, x.order, x.title)
        )
