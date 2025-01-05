"""Types for code analysis and context extraction."""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class APIChange:
    """Represents a change in the public API."""

    path: str
    change_type: str  # 'added', 'modified', 'removed', 'deprecated'
    old_signature: str
    new_signature: str
    breaking: bool
    affected_endpoints: List[str]
    commit_hash: str


@dataclass
class DependencyUpdate:
    """Represents a change in project dependencies."""

    name: str
    old_version: str
    new_version: str
    update_type: str  # 'major', 'minor', 'patch'
    changelog_url: str
    breaking: bool
    commit_hash: str


@dataclass
class SchemaChange:
    """Represents a change in data schemas."""

    entity: str
    change_type: str
    details: Dict[str, Any]
    migration_required: bool
    backward_compatible: bool
    commit_hash: str


@dataclass
class ChangeAnalysis:
    """Analyzed change combining commit and technical context."""

    commit_hash: str
    timestamp: datetime
    title: str
    description: str
    impact: str
    technical_details: Optional[Dict]
    breaking: bool
    source_metadata: Dict[str, Any]  # For debugging/tracing


@dataclass
class CodeContext:
    """Context extracted from code analysis."""

    api_changes: List[APIChange]
    dependency_updates: List[DependencyUpdate]
    test_coverage_changes: Dict[str, float]
    documentation_updates: List[str]
    schema_changes: List[SchemaChange]

    def has_breaking_changes(self) -> bool:
        """Check if any changes are breaking."""
        return any(
            [
                any(change.breaking for change in self.api_changes),
                any(update.breaking for update in self.dependency_updates),
                any(change.migration_required for change in self.schema_changes),
            ]
        )
