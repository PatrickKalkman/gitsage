"""Analysis Planning Node using LangChain and Groq for commit analysis."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from git import Repo, Commit
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser


@dataclass
class CommitClarity:
    """Assessment of a commit's clarity and completeness."""

    commit_hash: str
    message_clarity: float
    needs_code_review: bool
    suggested_improvements: List[str]
    code_changes_summary: Optional[str] = None


class AnalysisPlanningNode:
    """Node for analyzing commit clarity and planning detailed analysis."""

    MESSAGE_ANALYSIS_TEMPLATE = """
    system
    You are an expert at analyzing git commits for clarity and completeness.
    Given a commit message,you analyze its effectiveness in communicating changes.
    Return a JSON object with your analysis.

    user
    Analyze this git commit message for clarity and completeness:

    COMMIT_MESSAGE: {commit_message}

    Evaluate and provide a JSON response with these keys:
    - message_clarity: float between 0 and 1
    - needs_code_review: boolean
    - suggested_improvements: list of strings
    - is_breaking_change: boolean

    assistant
    """

    CODE_ANALYSIS_TEMPLATE = """
    system
    You are an expert at analyzing git code changes and providing clear summaries.
    Analyze the provided changes and explain their impact clearly.

    user
    Analyze these git commit changes:

    COMMIT_MESSAGE: {commit_message}
    CODE_CHANGES: {code_changes}

    Provide a JSON response with these keys:
    - functional_changes: string describing what changed functionally
    - impact_assessment: string describing the impact on the codebase
    - risk_factors: list of potential risks or considerations
    - technical_details: string with relevant technical details

    assistant
    """

    def __init__(self, api_key: str, model_name: str = "llama3-groq-70b-8192-tool-use-preview"):
        """Initialize with Groq configuration."""
        self.llm = ChatGroq(groq_api_key=api_key, model=model_name)

        # Initialize prompt templates
        self.message_analyzer = (
            PromptTemplate(
                template=self.MESSAGE_ANALYSIS_TEMPLATE,
                input_variables=["commit_message"],
            )
            | self.llm
            | JsonOutputParser()
        )

        self.code_analyzer = (
            PromptTemplate(
                template=self.CODE_ANALYSIS_TEMPLATE,
                input_variables=["commit_message", "code_changes"],
            )
            | self.llm
            | JsonOutputParser()
        )

    def _get_commit_diff(self, repo: Repo, commit: Commit) -> str:
        """Extract code changes from a commit."""
        parent = commit.parents[0] if commit.parents else None
        if parent:
            diff = repo.git.diff(parent.hexsha, commit.hexsha)
        else:
            diff = repo.git.show(commit.hexsha)
        return diff

    async def analyze_commit(self, repo: Repo, commit: Commit) -> CommitClarity:
        """Analyze a single commit for clarity and needed analysis."""
        # Analyze commit message
        message_analysis = await self.message_analyzer.ainvoke({"commit_message": commit.message})

        code_summary = None
        if message_analysis["needs_code_review"]:
            diff = self._get_commit_diff(repo, commit)
            code_analysis = await self.code_analyzer.ainvoke(
                {
                    "commit_message": commit.message,
                    "code_changes": diff[:4000],  # Truncate to avoid token limits
                }
            )
            code_summary = code_analysis["functional_changes"]

        return CommitClarity(
            commit_hash=commit.hexsha,
            message_clarity=float(message_analysis["message_clarity"]),
            needs_code_review=bool(message_analysis["needs_code_review"]),
            suggested_improvements=message_analysis["suggested_improvements"],
            code_changes_summary=code_summary,
        )

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the planning node's analysis."""
        repo = Repo(state["repository_path"])
        commits = state["commits"]

        # Analyze each commit
        clarity_assessments = []
        for commit_info in commits:
            commit = repo.commit(commit_info.hash)
            assessment = await self.analyze_commit(repo, commit)
            clarity_assessments.append(assessment)

        # Determine overall analysis strategy
        unclear_commits = [a for a in clarity_assessments if a.needs_code_review]
        breaking_changes = any(
            a.message_clarity < 0.6 or "breaking" in str(a.code_changes_summary).lower() for a in clarity_assessments
        )

        # Update state with analysis results
        new_state = {
            **state,
            "commit_clarity": clarity_assessments,
            "commits_needing_review": [a.commit_hash for a in unclear_commits],
            "analysis_plan": {
                "target_audiences": [
                    "developers",
                    "technical_leads",
                    "end_users" if not breaking_changes else "migration_team",
                ],
                "required_formats": ["markdown", "html"],
                "focus_areas": ["code_changes", "breaking_changes", "technical_debt"]
                if unclear_commits
                else ["features", "improvements"],
                "additional_analysis_needed": bool(unclear_commits),
                "risk_level": "high" if breaking_changes else "normal",
            },
        }

        return new_state


def load_planning_node(api_key: str, model_name: str = "mixtral-8x7b-32768") -> AnalysisPlanningNode:
    """Factory function to create a configured AnalysisPlanningNode."""
    return AnalysisPlanningNode(api_key, model_name)
