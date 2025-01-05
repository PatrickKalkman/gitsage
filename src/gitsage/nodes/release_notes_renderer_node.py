"""Release Notes Renderer Node for converting analyzed changes into formatted content."""

import os
from typing import Optional, List
from datetime import datetime
from loguru import logger

from gitsage.models.state import AgentState
from gitsage.models.render import RenderedContent, RenderedVersion
from gitsage.models.analysis import ChangeAnalysis


def _format_breaking_changes(changes: List[ChangeAnalysis]) -> str:
    """Format breaking changes section."""
    if not changes:
        return ""

    content = ["## ⚠️ Breaking Changes\n"]
    for change in changes:
        content.append(f"- **{change.title}**  \n  {change.description}")
        if change.impact:
            content.append(f"  \n  Impact: {change.impact}")
        content.append("")  # Empty line between entries

    return "\n".join(content)


def _format_regular_changes(changes: List[ChangeAnalysis]) -> str:
    """Format non-breaking changes section."""
    if not changes:
        return ""

    content = ["## Changes & Improvements\n"]
    for change in changes:
        content.append(f"- **{change.title}**  \n  {change.description}")
        content.append("")  # Empty line between entries

    return "\n".join(content)


def _generate_summary(state: AgentState) -> str:
    """Generate a summary section based on impact analysis."""
    impact = state["impact_analysis"]
    breaking_count = len(impact.breaking_changes)
    total_count = len(impact.changes)
    regular_count = total_count - breaking_count

    summary = ["## Summary\n"]
    summary.append(f"This release includes {total_count} changes:")
    if breaking_count:
        summary.append(f"- {breaking_count} breaking changes")
    summary.append(f"- {regular_count} improvements and fixes\n")

    # Add risk level if not normal
    if impact.risk_level.lower() != "normal":
        summary.append(f"**Note:** This release has been marked as `{impact.risk_level}` risk.\n")

    return "\n".join(summary)


def _get_project_info(state: AgentState) -> tuple[str, Optional[str], datetime]:
    """Extract project name, version and date information."""
    # Extract project name from repo path
    repo_path = state.get("repo_path", "")
    project_name = os.path.basename(repo_path)

    # Clean up project name (remove .git if present)
    project_name = project_name.replace(".git", "").replace("-", " ").replace("_", " ").title()

    version = None
    date = datetime.now()

    # Try to get version from last tag
    if state.get("last_tag"):
        version = state["last_tag"]

    # Get date from most recent commit if available
    if state.get("commits"):
        latest_commit = max(state["commits"], key=lambda x: x.date)
        date = latest_commit.date

    return project_name, version, date


async def release_notes_renderer_node(state: AgentState) -> AgentState:
    """Convert analyzed changes into formatted release notes."""
    try:
        logger.info("Executing Release Notes Renderer Node")

        # Extract project info, version and date
        project_name, version, date = _get_project_info(state)
        version_str = f" {version}" if version else ""

        # Generate markdown content
        content_parts = [
            f"# {project_name} Release Notes{version_str}",
            f"Generated on: {date.strftime('%Y-%m-%d')}\n",
            _generate_summary(state),
            _format_breaking_changes(state["impact_analysis"].breaking_changes),
            _format_regular_changes(
                [c for c in state["impact_analysis"].changes if c not in state["impact_analysis"].breaking_changes]
            ),
        ]

        markdown_content = "\n".join(filter(None, content_parts))

        # Create rendered version
        markdown_version = RenderedVersion(
            format_type="markdown",
            content=markdown_content,
            template_used="basic_markdown",
            generation_date=date.isoformat(),
            metadata={
                "version": version,
                "risk_level": state["impact_analysis"].risk_level,
                "target_audiences": state["impact_analysis"].target_audiences,
            },
        )

        # Create rendered content
        rendered_content = RenderedContent(markdown=markdown_content, versions={"markdown": markdown_version})

        # Update state
        state["rendered_content"] = rendered_content
        return state

    except Exception as e:
        logger.error(f"Error in Release Notes Renderer: {str(e)}")
        state.setdefault("errors", []).append(
            {"node": "release_notes_renderer", "error": str(e), "timestamp": datetime.now()}
        )
        return state
