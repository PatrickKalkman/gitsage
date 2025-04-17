"""GitSage workflow integration using LangGraph for orchestration."""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from loguru import logger

from gitsage.models.state import AgentState
from gitsage.nodes.analysis_node import analysis_node
from gitsage.nodes.commit_discovery_node import commit_discovery_node
from gitsage.nodes.context_node import context_node
from gitsage.nodes.planning_node import planning_node
from gitsage.nodes.release_notes_renderer_node import release_notes_renderer_node


def create_workflow(config: Dict[str, Any]) -> StateGraph:
    """Create the GitSage workflow graph."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("commit_discovery_node", commit_discovery_node)
    workflow.add_node("planning_node", planning_node)
    workflow.add_node("context_analysis_node", context_node)
    workflow.add_node("impact_analysis_node", analysis_node)
    workflow.add_node("release_notes_renderer_node", release_notes_renderer_node)

    workflow.set_entry_point("commit_discovery_node")

    # Define edges
    workflow.add_edge("commit_discovery_node", "planning_node")
    workflow.add_edge("planning_node", "context_analysis_node")
    workflow.add_edge("context_analysis_node", "impact_analysis_node")
    workflow.add_edge("impact_analysis_node", "release_notes_renderer_node")
    workflow.add_edge("release_notes_renderer_node", END)

    return workflow.compile()


async def run_workflow_async(config: Dict[str, Any]) -> AgentState:
    """Run the GitSage workflow asynchronously and return the final state."""
    initial_state: AgentState = {
        "repo_path": config["repo_path"],
        "groq_api_key": config["groq_api_key"],
        "model": config["model"],
        "errors": [],
        "warnings": [],
    }

    app = create_workflow(config)
    final_state = None
    async for state in app.astream(initial_state):
        final_state = list(state.values())[0]
        if "errors" in final_state and final_state["errors"]:
            logger.error("Errors encountered:", final_state["errors"])

    return final_state


def run_workflow(config: Dict[str, Any]) -> AgentState:
    """Synchronous wrapper for the async workflow."""
    return asyncio.run(run_workflow_async(config))


def main():
    parser = argparse.ArgumentParser(description="Generate release notes using GitSage")
    parser.add_argument("--repo-path", type=str, help="Path to the Git repository", default=".")
    parser.add_argument("--output-dir", type=str, help="Output directory for release notes", default="release_notes")
    parser.add_argument(
        "--model",
        type=str,
        choices=["meta-llama/llama-4-scout-17b-16e-instruct", "llama-3.1-8b-instant"],
        help="LLM model to use",
        default="llama-3.1-8b-instant",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        logger.error("GROQ_API_KEY environment variable is not set")
        sys.exit(1)

    if not args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    config = {
        "repo_path": os.path.abspath(args.repo_path),
        "groq_api_key": groq_api_key,
        "output_dir": args.output_dir,
        "model": args.model,
    }

    logger.info(f"Analyzing repository: {config['repo_path']}")
    final_state = run_workflow(config)

    logger.info("Workflow completed!")
    logger.info(f"Analyzed {final_state['commit_count']} commits")
    logger.info(f"Found {len(final_state['code_context'].api_changes)} API changes")
    logger.info(f"Found {len(final_state['code_context'].dependency_updates)} dependency updates")
    logger.info(f"Found {len(final_state['code_context'].schema_changes)} schema changes")

    if final_state.get("rendered_content"):
        os.makedirs(args.output_dir, exist_ok=True)
        version = final_state.get("last_tag", "unreleased")
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"release_notes_{version}_{date_str}.md"
        filepath = os.path.join(args.output_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(final_state["rendered_content"].markdown)
            logger.info(f"Release notes saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save release notes: {str(e)}")

    if final_state.get("errors"):
        logger.error("Errors encountered during processing:")
        for error in final_state["errors"]:
            logger.error(f"- {error['node']}: {error['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
