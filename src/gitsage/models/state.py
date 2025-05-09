"""State management types for the GitSage system."""

from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict

from .base import CommitInfo
from .analysis import AnalysisPlan, ImpactAnalysis
from .code import CodeContext
from .render import RenderedContent


class AgentState(TypedDict):
    """
    Shared state passed between nodes.
    Each node adds or modifies specific fields.
    """

    # Input
    repo_path: str
    groq_api_key: str
    model: str

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

    # Release Notes Output
    rendered_content: RenderedContent

    # Global State
    repository_path: str
    generation_date: datetime
    config: Dict[str, Any]
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
