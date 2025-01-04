# from typing import Dict, List, Optional, Set
# from dataclasses import dataclass
# from datetime import datetime
# from langchain.schema import Document
# from langgraph.prebuilt import ToolExecutor
# from git import Repo, Commit
# import difflib

# from .state import AgentState


# @dataclass
# class CodeChangeContext:
#     """Represents the contextual information about code changes."""

#     file_path: str
#     diff: str
#     change_type: str  # 'added', 'modified', 'deleted'
#     language: str
#     semantic_type: Optional[str] = None  # e.g., 'feature', 'bugfix', 'refactor'


# class CodeContextNode:
#     """Node responsible for enriching commit data with code context."""

#     def __init__(self, repo_path: str):
#         self.repo = Repo(repo_path)
#         self.language_patterns = {
#             "python": [".py"],
#             "javascript": [".js", ".jsx", ".ts", ".tsx"],
#             "java": [".java"],
#             # Add more language patterns as needed
#         }

#     def _detect_language(self, file_path: str) -> str:
#         """Detect programming language based on file extension."""
#         extension = file_path.split(".")[-1] if "." in file_path else ""
#         for language, patterns in self.language_patterns.items():
#             if any(file_path.endswith(pattern) for pattern in patterns):
#                 return language
#         return "unknown"

#     def _analyze_diff(self, diff: str) -> Dict:
#         """Analyze diff content for semantic meaning."""
#         lines_added = len([line for line in diff.split("\n") if line.startswith("+")])
#         lines_removed = len([line for line in diff.split("\n") if line.startswith("-")])

#         return {
#             "lines_added": lines_added,
#             "lines_removed": lines_removed,
#             "net_changes": lines_added - lines_removed,
#             "is_large_change": (lines_added + lines_removed) > 100,
#         }

#     def _get_file_diff(self, commit: Commit, file_path: str) -> str:
#         """Get the diff for a specific file in a commit."""
#         try:
#             parent = commit.parents[0] if commit.parents else None
#             if parent:
#                 diffs = commit.diff(parent)
#                 for diff_item in diffs:
#                     if diff_item.a_path == file_path or diff_item.b_path == file_path:
#                         return diff_item.diff.decode("utf-8")
#         except Exception as e:
#             print(f"Error getting diff for {file_path}: {str(e)}")
#         return ""

#     def _determine_change_type(self, commit: Commit, file_path: str) -> str:
#         """Determine if the file was added, modified, or deleted."""
#         diffs = commit.diff(commit.parents[0] if commit.parents else None)
#         for diff_item in diffs:
#             if diff_item.a_path == file_path or diff_item.b_path == file_path:
#                 if diff_item.new_file:
#                     return "added"
#                 elif diff_item.deleted_file:
#                     return "deleted"
#                 return "modified"
#         return "unknown"

#     def _infer_semantic_type(self, diff: str, commit_message: str, needs_review: bool) -> str:
#         """Infer the semantic type of changes based on diff and commit message patterns."""
#         diff_lower = diff.lower()
#         msg_lower = commit_message.lower()

#         # Pattern matching for common change types
#         patterns = {
#             "feature": ["feat", "add", "new", "implement"],
#             "bugfix": ["fix", "bug", "issue", "patch", "solve"],
#             "refactor": ["refactor", "clean", "restructure", "improve"],
#             "style": ["style", "format", "lint"],
#             "docs": ["doc", "comment", "readme"],
#             "test": ["test", "spec", "assert"],
#             "build": ["build", "dep", "package"],
#         }

#         for semantic_type, keywords in patterns.items():
#             if any(keyword in msg_lower or keyword in diff_lower for keyword in keywords):
#                 return semantic_type

#         return "unknown" if needs_review else "feature"

#     def process(self, state: Dict) -> Dict:
#         """Process the commit and enrich it with code context."""
#         commit_sha = state.get("current_commit")
#         if not commit_sha:
#             return state

#         commit = self.repo.commit(commit_sha)
#         code_contexts: List[CodeChangeContext] = []

#         # Get clarity assessment from planning node
#         commit_clarity = next((c for c in state.get("commit_clarity", []) if c.commit_hash == commit_sha), None)
#         needs_review = commit_clarity.needs_code_review if commit_clarity else False

#         # Process each changed file in the commit
#         for file_path in commit.stats.files.keys():
#             change_type = self._determine_change_type(commit, file_path)
#             diff = self._get_file_diff(commit, file_path)
#             language = self._detect_language(file_path)

#             # Infer semantic type based on changes and clarity assessment
#             semantic_type = self._infer_semantic_type(diff, commit.message, needs_review)

#             context = CodeChangeContext(
#                 file_path=file_path, diff=diff, change_type=change_type, language=language, semantic_type=semantic_type
#             )
#             code_contexts.append(context)

#         # Update the state with enriched context and analysis plan
#         state["code_contexts"] = code_contexts
#         state["diff_analysis"] = {file_path: self._analyze_diff(context.diff) for context in code_contexts}

#         # Add additional context based on planning node's analysis
#         if "analysis_plan" in state:
#             state["context_summary"] = {
#                 "primary_changes": [ctx for ctx in code_contexts if ctx.semantic_type in ["feature", "bugfix"]],
#                 "secondary_changes": [ctx for ctx in code_contexts if ctx.semantic_type not in ["feature", "bugfix"]],
#                 "risk_level": state["analysis_plan"]["risk_level"],
#                 "requires_migration": any(diff["is_large_change"] for diff in state["diff_analysis"].values()),
#             }

#         return state

#     @staticmethod
#     def get_relevant_code_segments(diff: str) -> List[str]:
#         """Extract relevant code segments from the diff."""
#         segments = []
#         current_segment = []

#         for line in diff.split("\n"):
#             if line.startswith(("+++", "---")):
#                 continue
#             if line.startswith("@@ "):
#                 if current_segment:
#                     segments.append("\n".join(current_segment))
#                     current_segment = []
#                 continue
#             if line.startswith(("+", "-")):
#                 current_segment.append(line)

#         if current_segment:
#             segments.append("\n".join(current_segment))

#         return segments


# # Example usage in the LangGraph pipeline
# def create_code_context_node(repo_path: str) -> ToolExecutor:
#     """Create a tool executor for the code context node."""
#     context_node = CodeContextNode(repo_path)
#     return ToolExecutor(tools=[context_node.process], state_key="agent_state")
