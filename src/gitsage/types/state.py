"""State management types for the GitSage system."""

from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict

from .base import CommitInfo
from .analysis import AnalysisPlan, ImpactAnalysis
from .code import CodeContext
from .content import ReleaseStructure
from .render import RenderedContent


class AgentState(TypedDict):
    """
    Shared state passed between nodes.
    Each node adds or modifies specific fields.
    """

    # CommitDiscovery Node Output
    commits: List[CommitInfo]
    commit_count: int
    context: str
    start_ref: Optional[str]
    end_ref: str
    last_tag: Optional[str]
    all_tags: List[str]

    # Analysis Planning Node Output
    analysis_plan: AnalysisPlan

    # Code Context Node Output
    code_context: CodeContext

    # Analysis Node Output
    impact_analysis: ImpactAnalysis

    # Release Organization Node Output
    release_structure: ReleaseStructure

    # Format Renderer Node Output
    rendered_content: RenderedContent

    # Global State
    repository_path: str
    generation_date: datetime
    config: Dict[str, Any]
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
