"""Analysis Planning Node using LangChain and Groq for commit analysis."""

from typing import List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from git import Repo, Commit
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser

from gitsage.types.state import AgentState
from gitsage.types.base import CommitInfo


@dataclass
class CommitClarity:
    """Assessment of a commit's clarity and completeness."""

    commit_hash: str
    message_clarity: float
    needs_code_review: bool
    suggested_improvements: List[str]
    code_changes_summary: Optional[str] = None


# LLM prompt templates
MESSAGE_ANALYSIS_TEMPLATE = """
You are an expert at analyzing git commits for clarity and completeness.
Given a commit message, analyze its effectiveness in communicating changes.

Commit message to analyze:
{commit_message}

Provide a JSON response with these keys:
- message_clarity: float between 0 and 1
- needs_code_review: boolean
- suggested_improvements: list of strings
- is_breaking_change: boolean
"""

CODE_ANALYSIS_TEMPLATE = """
You are an expert at analyzing git code changes and providing clear summaries.

Analyze these changes:
Commit Message: {commit_message}
Code Changes: {code_changes}

Provide a JSON response with these keys:
- functional_changes: string describing what changed functionally
- impact_assessment: string describing the impact
- risk_factors: list of potential risks
- technical_details: string with relevant details
"""


async def analyze_single_commit(commit: Commit, message_analyzer: Any, state: AgentState) -> CommitClarity:
    """Analyze a single commit with error handling."""
    try:
        # Analyze commit message
        message_analysis = await message_analyzer.ainvoke({"commit_message": commit.message})

        return CommitClarity(
            commit_hash=commit.hexsha,
            message_clarity=float(message_analysis["message_clarity"]),
            needs_code_review=bool(message_analysis["needs_code_review"]),
            suggested_improvements=message_analysis["suggested_improvements"],
        )

    except Exception as e:
        # Record error and return None
        state["errors"].append(
            {"node": "planning_node", "commit": commit.hexsha, "error": str(e), "timestamp": datetime.now()}
        )
        return None


async def planning_node(state: AgentState) -> AgentState:
    """Execute the planning node's analysis with comprehensive error handling."""
    try:
        # Initialize LLM and chains
        if "groq_api_key" not in state:
            raise ValueError("groq_api_key is required in AgentState")

        llm = ChatGroq(groq_api_key=state["groq_api_key"], model="mixtral-8x7b-32768")

        message_analyzer = (
            PromptTemplate(template=MESSAGE_ANALYSIS_TEMPLATE, input_variables=["commit_message"])
            | llm
            | JsonOutputParser()
        )

        # Initialize collections
        repo = Repo(state["repo_path"])
        commits: List[CommitInfo] = state["commits"]
        clarity_assessments: List[CommitClarity] = []
        state.setdefault("errors", [])

        # Process each commit
        for commit_info in commits:
            try:
                commit = repo.commit(commit_info.hash)
                assessment = await analyze_single_commit(
                    commit=commit,
                    message_analyzer=message_analyzer,
                    state=state,
                )
                if assessment:
                    clarity_assessments.append(assessment)

            except Exception as e:
                state["errors"].append(
                    {"node": "planning_node", "commit": commit_info.hash, "error": str(e), "timestamp": datetime.now()}
                )

        # Analyze results
        unclear_commits = [a.commit_hash for a in clarity_assessments if a.needs_code_review]

        breaking_changes = any(
            a.message_clarity < 0.6 or (a.code_changes_summary and "breaking" in a.code_changes_summary.lower())
            for a in clarity_assessments
        )

        # Update state with analysis results
        state["commit_clarity"] = clarity_assessments
        state["commits_needing_review"] = unclear_commits
        state["analysis_plan"] = {
            "target_audiences": [
                "developers",
                "technical_leads",
                "end_users" if not breaking_changes else "migration_team",
            ],
            "required_formats": ["markdown", "html"],
            "focus_areas": (
                ["code_changes", "breaking_changes", "technical_debt"]
                if unclear_commits
                else ["features", "improvements"]
            ),
            "additional_analysis_needed": bool(unclear_commits),
            "risk_level": "high" if breaking_changes else "normal",
        }

        return state

    except Exception as e:
        # Handle top-level errors
        state.setdefault("errors", []).append({"node": "planning_node", "error": str(e), "timestamp": datetime.now()})
        return state
