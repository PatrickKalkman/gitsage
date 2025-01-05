"""Code Context Node for extracting technical changes from commits."""

from typing import List, Dict, Any, Set
from git import Repo, Commit, NULL_TREE
import re
from pathlib import Path

from loguru import logger
from gitsage.models.state import AgentState
from gitsage.models.code import APIChange, DependencyUpdate, SchemaChange, CodeContext


def extract_file_changes(commit: Commit) -> Dict[str, Any]:
    """Extract detailed file changes from a commit."""
    parent = commit.parents[0] if commit.parents else NULL_TREE
    diff = commit.diff(parent, create_patch=True)

    changes = {
        "added_files": set(),
        "modified_files": set(),
        "deleted_files": set(),
        "patches": {},
        "file_types": set(),
    }

    for d in diff:
        file_path = d.b_path or d.a_path
        if file_path:
            extension = Path(file_path).suffix
            changes["file_types"].add(extension)

        if d.new_file:
            changes["added_files"].add(file_path)
        elif d.deleted_file:
            changes["deleted_files"].add(file_path)
        else:
            changes["modified_files"].add(file_path)

        if d.diff:
            changes["patches"][file_path] = d.diff.decode("utf-8")

    return changes


def identify_api_changes(changes: Dict[str, Any], commit_hash: str) -> List[APIChange]:
    """Extract API changes from modified files."""
    api_changes = []
    api_patterns = {
        ".py": r"^\s*def\s+(\w+)\s*\([^)]*\)|^\s*class\s+(\w+).*:",
        ".js": r"^\s*(function|const)\s+(\w+)\s*\([^)]*\)|^\s*class\s+(\w+)",
        ".java": r"^\s*(public|private|protected)\s+\w+\s+(\w+)\s*\([^)]*\)",
        ".go": r"^\s*func\s+(\w+)\s*\([^)]*\)",
    }

    for file_path, patch in changes["patches"].items():
        extension = Path(file_path).suffix
        # Only process API-related files
        if not any(term in file_path.lower() for term in ["api", "controller", "service", "handler"]):
            continue

        if extension in api_patterns:
            pattern = api_patterns[extension]

            # Process each line of the patch
            removed_apis = []
            added_apis = []

            for line in patch.split("\n"):
                line = line.strip()
                if line:  # Skip empty lines
                    is_removal = line.startswith("-")
                    is_addition = line.startswith("+")

                    if is_removal or is_addition:
                        line = line[1:].strip()

                    matches = re.search(pattern, line)
                    if matches:
                        # Get the first non-None group from the match
                        api_name = next(g for g in matches.groups() if g is not None)
                        if is_removal:
                            removed_apis.append((api_name, line))
                        elif is_addition:
                            added_apis.append((api_name, line))

            # Only create an APIChange if there are actual changes
            if removed_apis or added_apis:
                api_changes.append(
                    APIChange(
                        path=file_path,
                        change_type="modified",
                        old_signature=str([api[1] for api in removed_apis]),
                        new_signature=str([api[1] for api in added_apis]),
                        breaking=bool(removed_apis),  # Breaking if any APIs were removed
                        affected_endpoints=[file_path],
                        commit_hash=commit_hash,
                    )
                )

    return api_changes


def detect_dependency_updates(changes: Dict[str, Any], commit_hash: str) -> List[DependencyUpdate]:
    """Extract dependency changes from package files."""
    updates = []
    dependency_patterns = {
        "requirements.txt": r"^([^=]+)==([^\s]+)",
        "package.json": r'"([^"]+)":\s*"([^"]+)"',
        "go.mod": r"require\s+([^\s]+)\s+([^\s]+)",
        "Cargo.toml": r'([^=\s]+)\s*=\s*"([^"]+)"',
    }

    for file_path, patch in changes["patches"].items():
        filename = Path(file_path).name
        if filename in dependency_patterns:
            pattern = dependency_patterns[filename]

            for line in patch.split("\n"):
                if line.startswith("+"):
                    matches = re.findall(pattern, line.lstrip("+"))
                    for pkg, version in matches:
                        updates.append(
                            DependencyUpdate(
                                name=pkg.strip(),
                                old_version="",  # Would need previous version context
                                new_version=version.strip(),
                                update_type="unknown",
                                changelog_url="",
                                breaking=False,
                                commit_hash=commit_hash,
                            )
                        )

    return updates


def analyze_schema_changes(changes: Dict[str, Any], commit_hash: str) -> List[SchemaChange]:
    """Extract schema changes from data model files."""
    schema_changes = []
    schema_patterns = {
        ".sql": r"(CREATE|ALTER|DROP)\s+TABLE",
        ".py": r"class\s+(\w+)\(.*\):",
        ".js": r"(type|interface)\s+(\w+)",
        "migration": r"(CreateTable|AddColumn|DropTable)",
    }

    for file_path, patch in changes["patches"].items():
        file_lower = file_path.lower()

        if any(term in file_lower for term in ["model", "schema", "migration", "entity"]):
            ext = Path(file_path).suffix
            for pattern_key, pattern in schema_patterns.items():
                if pattern_key in ext or pattern_key in file_lower:
                    matches = re.findall(pattern, patch)
                    if matches:
                        schema_changes.append(
                            SchemaChange(
                                entity=Path(file_path).stem,
                                change_type="modified",
                                details={"matches": matches},
                                migration_required="migration" in file_lower,
                                backward_compatible=not any(
                                    term in patch.lower() for term in ["drop", "delete", "remove"]
                                ),
                                commit_hash=commit_hash,
                            )
                        )

    return schema_changes


def context_node(state: AgentState) -> AgentState:
    """Execute the context extraction node."""
    try:
        if "repo_path" not in state:
            raise ValueError("repo_path is required in AgentState")

        logger.info("Executing Context Node")
        repo = Repo(state["repo_path"])
        commits = state["commits"]

        # Track cumulative changes
        all_api_changes: List[APIChange] = []
        all_dependency_updates: List[DependencyUpdate] = []
        all_schema_changes: List[SchemaChange] = []
        affected_file_types: Set[str] = set()

        # Process each commit
        for commit_info in commits:
            try:
                commit = repo.commit(commit_info.hash)
                changes = extract_file_changes(commit)

                # Update cumulative changes
                affected_file_types.update(changes["file_types"])
                all_api_changes.extend(identify_api_changes(changes, commit_info.hash))
                all_dependency_updates.extend(detect_dependency_updates(changes, commit_info.hash))
                all_schema_changes.extend(analyze_schema_changes(changes, commit_info.hash))

            except Exception as e:
                state.setdefault("errors", []).append(
                    {"node": "context_node", "commit": commit_info.hash, "error": str(e)}
                )

        # Create CodeContext and update state
        code_context = CodeContext(
            api_changes=all_api_changes,
            dependency_updates=all_dependency_updates,
            schema_changes=all_schema_changes,
            documentation_updates=[],  # Left for Analysis Node
            test_coverage_changes={},  # Would need test coverage analysis
        )

        # Update state with technical context
        state["code_context"] = code_context
        state["affected_file_types"] = list(affected_file_types)

        return state

    except Exception as e:
        state.setdefault("errors", []).append({"node": "context_node", "error": str(e)})
        return state
