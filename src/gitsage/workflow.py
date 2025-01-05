"""GitSage workflow integration using LangGraph for orchestration."""

from typing import Dict, Any
import asyncio
import os
import sys
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from gitsage.models.state import AgentState
from gitsage.nodes.commit_discovery_node import commit_discovery_node
from gitsage.nodes.planning_node import planning_node
from gitsage.nodes.context_node import context_node
from gitsage.nodes.analysis_node import analysis_node
from gitsage.nodes.release_notes_renderer_node import release_notes_renderer_node


def create_workflow(config: Dict[str, Any]) -> StateGraph:
    """
    Create the GitSage workflow graph.
    """
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
    """
    Run the GitSage workflow asynchronously and return the final state.
    """
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
            print("Errors encountered:", final_state["errors"])

    return final_state


def run_workflow(config: Dict[str, Any]) -> AgentState:
    """
    Synchronous wrapper for the async workflow.
    """
    return asyncio.run(run_workflow_async(config))


if __name__ == "__main__":
    load_dotenv()

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        logger.error("GROQ_API_KEY environment variable is not set")
        sys.exit(1)

    config = {
        "repo_path": "/Users/patrickkalkman/projects/sb/Video-On-Demand-TV-Launcher",
        "groq_api_key": groq_api_key,
        "output_dir": "release_notes",
        "model": "mixtral-8x7b-32768",
    }
    final_state = run_workflow(config)

    logger.info("Workflow completed!")
    logger.info(f"Analyzed {final_state['commit_count']} commits")
    logger.info(f"Found {len(final_state['code_context'].api_changes)} API changes")
    logger.info(f"Found {len(final_state['code_context'].dependency_updates)} dependency updates")
    logger.info(f"Found {len(final_state['code_context'].schema_changes)} schema changes")

    # Add logging for rendered content
    if final_state.get("rendered_content"):
        logger.info("Successfully generated release notes")
        if final_state["rendered_content"].markdown:
            # Create output directory if it doesn't exist
            output_dir = config.get("output_dir", "release_notes")
            os.makedirs(output_dir, exist_ok=True)

            # Generate filename using version and date
            version = final_state.get("last_tag", "unreleased")
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"release_notes_{version}_{date_str}.md"
            filepath = os.path.join(output_dir, filename)

            # Save markdown content
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(final_state["rendered_content"].markdown)
                logger.info(f"Release notes saved to: {filepath}")
            except Exception as e:
                logger.error(f"Failed to save release notes: {str(e)}")
                final_state["errors"].append(
                    {
                        "node": "workflow",
                        "error": f"Failed to save release notes: {str(e)}",
                        "timestamp": datetime.now(),
                    }
                )

    if final_state.get("errors"):
        logger.info("Errors encountered during processing:")
        for error in final_state["errors"]:
            logger.info(f"- {error['node']}: {error['error']}")
