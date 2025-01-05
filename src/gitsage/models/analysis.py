"""Types related to release note analysis and planning."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from .code import ChangeAnalysis


@dataclass
class AnalysisPlan:
    """Planning information for release note generation."""

    target_audiences: List[str]
    required_formats: List[str]
    focus_areas: List[str]
    custom_categories: Optional[Dict[str, List[str]]] = None
    additional_analysis_needed: bool = False
    risk_level: str = "normal"


@dataclass
class ImpactAnalysis:
    """Analysis of changes and their impact."""

    changes: List[ChangeAnalysis]  # All analyzed changes
    breaking_changes: List[ChangeAnalysis]  # Changes marked as breaking
    target_audiences: List[str]  # Who needs to know about these changes
    risk_level: str  # Risk assessment of the changes

    # Additional metadata for detailed analysis
    security_implications: List[Dict[str, Any]] = None
    performance_impacts: List[Dict[str, Any]] = None
    compatibility_notes: List[str] = None
    upgrade_requirements: List[str] = None
