"""Types related to release note analysis and planning."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


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

    breaking_changes: List[Dict[str, Any]]
    security_implications: List[Dict[str, Any]]
    performance_impacts: List[Dict[str, Any]]
    compatibility_notes: List[str]
    upgrade_requirements: List[str]
