# GitSage: AI-Powered Release Notes Generator

GitSage transforms your Git commit history into polished, user-friendly release notes by combining large language models with intelligent code analysis. This tool bridges the gap between developer activities and user documentation, automating the creation of meaningful release notes that serve both technical and non-technical audiences.

## Key Features

- Intelligent commit analysis that understands both message content and code changes
- Context-aware processing that maintains clarity even with minimal commit messages
- Automated categorization of changes based on impact and significance
- Structured output that clearly communicates technical updates to users
- Support for multiple output formats with Markdown as the default
- Integration with modern LLM services through LangChain

## Getting Started

GitSage leverages UV's streamlined approach to Python package management and execution, simplifying the setup process while ensuring consistent dependency resolution across environments.

### Prerequisites

- Python 3.10 or higher
- Git
- A Groq API key

### Installation

1. Install UV, which combines dependency management and execution in a single tool:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone the GitSage repository:

```bash
git clone https://github.com/PatrickKalkman/gitsage
cd gitsage
```

3. Configure your environment by creating a `.env` file in the project root:

```bash
echo "GROQ_API_KEY=your-api-key-here" > .env
```

### Running GitSage

UV's integrated run command handles both dependency installation and execution. For basic analysis of a repository:

```bash
uv run python ./src/gitsage/workflow.py --repo-path /path/to/your/repo
```

For more control over the analysis process, GitSage supports additional parameters:

```bash
uv run python ./src/gitsage/workflow.py \
  --repo-path /path/to/your/repo \
  --output-dir release_notes \
  --model mixtral-8x7b-32768 \
  --verbose
```

The UV run command ensures all dependencies are properly resolved before execution, eliminating the need for separate virtual environment management steps.

## Output Example

GitSage generates structured release notes that clearly communicate changes to users. Here's an example output:

```markdown
# Gitsage Release Notes v0.8.2
Generated on: 2025-01-08

## Summary
This release includes 2 changes:
- 2 improvements and fixes

**Note:** This release has been marked as `high` impact

## Changes & Improvements
- **Fixed an issue with a test**
  A fix was implemented to resolve an issue discovered during testing

- **Code Prompt Removed from Planning Node, CLI Updates**
  The code prompt has been removed from the planning phase for improved efficiency
```

## Architecture

GitSage employs a node-based architecture using LangGraph, maintaining contextual awareness throughout the release notes generation process. The system processes Git commits through five specialized nodes:

1. Commit Discovery: Retrieves and organizes repository changes
2. Analysis Planning: Evaluates commit quality and plans processing strategy
3. Code Context: Performs deep analysis of code modifications
4. Analysis: Synthesizes commit information with technical context
5. Release Notes Renderer: Transforms analysis into polished documentation

## Contributing

We welcome contributions! Please feel free to submit pull requests, report bugs, or suggest new features through our issue tracker.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

GitSage builds upon several excellent open-source projects and services:

- LangChain for LLM workflow management
- Groq for language model services
- UV for Python package management
- GitPython for repository interaction

For more detailed information about the implementation and architecture, please refer to the source code documentation.