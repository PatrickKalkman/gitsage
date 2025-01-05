"""Analysis Node for synthesizing commit and code analysis into release notes content."""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser

from gitsage.models.state import AgentState
from gitsage.models.analysis import ImpactAnalysis


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


# LLM prompt templates
CHANGE_ANALYSIS_TEMPLATE = """
You are an expert at analyzing software changes for release notes.
Analyze this change combining commit information and technical context.

Commit Information:
{commit_info}

Technical Context:
{technical_context}

Return a strict JSON response with exactly these fields as shown in this example:
{{
    "title": "A clear, concise title",
    "description": "Detailed explanation",
    "impact": "User-facing impact description",
    "breaking": false
}}

Important JSON formatting rules:
1. Do not escape underscores (_)
2. Use only \n for newlines
3. No additional fields
4. No comments
5. Keep it as a single-line JSON without pretty printing
"""


def _create_technical_context(commit_hash: str, code_context: Any) -> Dict[str, Any]:
    """
    Extract relevant technical context for a specific commit.
    Uses direct commit hash matching since we now store commit references.
    """
    context = {"api_changes": [], "dependency_updates": [], "schema_changes": []}

    # Extract API changes for this commit
    for change in code_context.api_changes:
        if change.commit_hash == commit_hash:
            context["api_changes"].append(
                {
                    "path": change.path,
                    "type": change.change_type,
                    "breaking": change.breaking,
                    "old_signature": change.old_signature,
                    "new_signature": change.new_signature,
                }
            )

    # Extract dependency updates by matching commit hash
    for dep in code_context.dependency_updates:
        if (hasattr(dep, "commit_hash") and dep.commit_hash == commit_hash) or (
            commit_hash in dep.__dict__.get("related_commits", [])
        ):
            context["dependency_updates"].append(
                {
                    "name": dep.name,
                    "old_version": dep.old_version,
                    "new_version": dep.new_version,
                    "breaking": dep.breaking,
                    "update_type": dep.update_type,
                    "changelog_url": dep.changelog_url,
                }
            )

    # Extract schema changes by matching commit hash and affected entities
    for schema in code_context.schema_changes:
        if (
            (hasattr(schema, "commit_hash") and schema.commit_hash == commit_hash)
            or (commit_hash in schema.__dict__.get("related_commits", []))
            or (
                schema.entity
                in [file.split("/")[-1].split(".")[0] for file in schema.__dict__.get("affected_files", [commit_hash])]
            )
        ):
            context["schema_changes"].append(
                {
                    "entity": schema.entity,
                    "type": schema.change_type,
                    "details": schema.details,
                    "migration_required": schema.migration_required,
                    "backward_compatible": schema.backward_compatible,
                }
            )

    return context


async def analyze_change(commit_info: Any, technical_context: Dict[str, Any], change_analyzer: Any) -> ChangeAnalysis:
    """Analyze a single change combining commit and technical information."""

    # Prepare analysis input
    analysis_input = {
        "commit_info": {
            "hash": commit_info.hash,
            "message": commit_info.message,
            "author": commit_info.author,
            "date": commit_info.date.isoformat(),
            "files_changed": commit_info.files_changed,
        },
        "technical_context": technical_context,
    }

    # Get LLM analysis
    try:
        analysis = await change_analyzer.ainvoke(analysis_input)

        return ChangeAnalysis(
            commit_hash=commit_info.hash,
            timestamp=commit_info.date,
            title=analysis["title"],
            description=analysis["description"],
            impact=analysis["impact"],
            technical_details=technical_context if technical_context else None,
            breaking=analysis["breaking"],
            source_metadata={
                "had_clear_commit": commit_info.hash not in analysis_input.get("commits_needing_review", []),
                "had_technical_context": bool(technical_context),
                "analysis_timestamp": datetime.now(),
            },
        )
    except Exception as e:
        raise ValueError(f"Error analyzing change {commit_info.hash}: {str(e)}")


async def analysis_node(state: AgentState) -> AgentState:
    """Execute the analysis node combining commit and technical context."""
    try:
        # Validate required state
        if "groq_api_key" not in state:
            raise ValueError("groq_api_key is required in AgentState")
        if "commits" not in state:
            raise ValueError("commits is required in AgentState")
        if "code_context" not in state:
            raise ValueError("code_context is required in AgentState")
        if "analysis_plan" not in state:
            raise ValueError("analysis_plan is required in AgentState")

        logger.info("Executing Analysis Node")
        # Initialize LLM and chains
        llm = ChatGroq(groq_api_key=state["groq_api_key"], model="mixtral-8x7b-32768")

        change_analyzer = (
            PromptTemplate(template=CHANGE_ANALYSIS_TEMPLATE, input_variables=["commit_info", "technical_context"])
            | llm
            | JsonOutputParser()
        )

        # Process each commit chronologically
        analyzed_changes: List[ChangeAnalysis] = []
        for commit in sorted(state["commits"], key=lambda x: x.date):
            logger.debug(f"Analyzing commit: {commit.hash} - {commit.message}")
            try:
                # Get technical context if available
                technical_context = _create_technical_context(commit.hash, state["code_context"])

                # Analyze change
                analysis = await analyze_change(
                    commit_info=commit, technical_context=technical_context, change_analyzer=change_analyzer
                )

                analyzed_changes.append(analysis)

            except Exception as e:
                state.setdefault("errors", []).append(
                    {"node": "analysis_node", "commit": commit.hash, "error": str(e), "timestamp": datetime.now()}
                )

        # Create impact analysis
        impact_analysis = ImpactAnalysis(
            changes=analyzed_changes,
            breaking_changes=[c for c in analyzed_changes if c.breaking],
            target_audiences=state["analysis_plan"]["target_audiences"],
            risk_level=state["analysis_plan"]["risk_level"],
        )

        # Update state
        state["impact_analysis"] = impact_analysis
        return state

    except Exception as e:
        # Handle top-level errors
        state.setdefault("errors", []).append({"node": "analysis_node", "error": str(e), "timestamp": datetime.now()})
        return state
