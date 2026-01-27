# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains community examples for the NVIDIA NeMo Agent Toolkit (NAT). The repository is organized into three main directories:

- **`examples/`** - Self-contained demonstrations of NAT features and integration patterns
- **`packages/`** - Reusable, production-ready NAT components that can be shared across examples and industries
- **`industries/`** - Complex, domain-specific workflows that showcase real-world applications

All components use Python 3.11+ and are managed with `uv` for fast dependency resolution.

## Building and Testing

### Initial Setup

```bash
# Clone and fetch LFS files
git clone https://github.com/NVIDIA/NeMo-Agent-Toolkit-Examples.git
cd NeMo-Agent-Toolkit-Examples
git lfs install
git lfs fetch
git lfs pull

# Create virtual environment
uv venv --python 3.13 --seed .venv
source .venv/bin/activate

# Install development dependencies
uv sync --dev
```

### Running Tests

```bash
# Run tests for all components
pytest

# Run tests for a specific component
pytest examples/mcp_rag_demo/tests/
pytest packages/nat_vanna_tool/tests/

# Run with coverage
pytest --cov
```

### Linting and Code Style

```bash
# Run all checks (pre-commit, pylint, copyright, documentation)
./ci/scripts/checks.sh

# Run only Python checks (pylint)
./ci/scripts/python_checks.sh

# Run pre-commit hooks manually
pre-commit run --all-files --show-diff-on-failure
```

The repository uses:
- **ruff** for linting and import sorting (configured in root `pyproject.toml`)
- **yapf** for code formatting (max line length: 120)
- **pylint** for Python code quality checks
- **vale** for documentation linting

### Installing Individual Components

```bash
# Install an example
uv pip install -e examples/mcp_rag_demo

# Install a package
uv pip install -e packages/nat_vanna_tool

# Install an industry workflow
uv pip install -e industries/asset_lifecycle_management

# Install with optional dependencies
uv pip install -e "packages/nat_vanna_tool[elasticsearch,postgres]"
```

## Architecture

### NAT Component Registration Pattern

All NAT components follow a plugin-based registration pattern using Python entry points:

1. **Define a config class** that inherits from `FunctionBaseConfig`:

```python
from nat.data_models.function import FunctionBaseConfig
from pydantic import Field

class MyToolConfig(FunctionBaseConfig, name="my_tool"):
    """Configuration for my tool."""
    param1: str = Field(description="Parameter 1")
    param2: int = Field(default=5, description="Parameter 2")
```

2. **Create a function with `@register_function` decorator**:

```python
from nat.cli.register_workflow import register_function
from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from pydantic import BaseModel, Field

@register_function(config_type=MyToolConfig)
async def my_tool_function(config: MyToolConfig, builder: Builder):
    """Tool implementation."""

    class MyToolInput(BaseModel):
        query: str = Field(description="User query")

    async def _execute(query: str) -> str:
        # Access config: config.param1, config.param2
        # Access builder for LLMs/embedders: await builder.get_llm(name)
        return f"Result: {query}"

    yield FunctionInfo.from_fn(
        _execute,
        input_schema=MyToolInput,
        description="Description of what this tool does"
    )
```

3. **Create a `register.py` entry point** that imports the function:

```python
# src/nat_my_component/register.py
from .my_tool import my_tool_function
```

4. **Declare the entry point in `pyproject.toml`**:

```toml
[project.entry-points.'nat.components']
nat_my_component = "nat_my_component.register"
```

### YAML Configuration Structure

NAT workflows are configured via hierarchical YAML files:

```yaml
general:
  use_uvloop: true
  telemetry:
    logging:
      console:
        _type: console
        level: DEBUG

llms:                          # Define available LLMs
  reasoning_llm:
    _type: nvidia_chat_model
    model_name: "meta/llama-3.1-70b-instruct"
    api_key: "${NVIDIA_API_KEY}"

embedders:                     # Define available embedders
  my_embedder:
    _type: nvidia_embeddings
    model_name: "nvidia/nv-embedqa-e5-v5"
    api_key: "${NVIDIA_API_KEY}"

functions:                     # Define available tools
  my_tool:
    _type: my_tool             # References the name from FunctionBaseConfig
    param1: "value"
    llm_name: "reasoning_llm"  # Reference to llms section

workflow:                      # Orchestrate the agent
  _type: react_agent
  tool_names: [my_tool]
  llm_name: reasoning_llm
  max_iterations: 10
```

Components reference each other by name strings (e.g., `llm_name: "reasoning_llm"`), which are resolved at runtime by NAT's builder.

### Directory Structure for New Components

Use `nat workflow create` to generate the recommended structure:

```
examples/$EXAMPLE_NAME/
├── configs/                   # Symlink to src/nat_$EXAMPLE_NAME/configs/
├── data/                      # [Optional] Symlink to src/nat_$EXAMPLE_NAME/data/
├── scripts/                   # [Optional] Setup scripts
├── src/
│   └── nat_$EXAMPLE_NAME/     # Module name must start with nat_
│       ├── configs/
│       │   └── config.yml
│       ├── data/              # [Optional] Data files
│       ├── __init__.py
│       └── register.py        # Entry point
├── tests/                     # pytest tests
├── README.md
└── pyproject.toml             # Must register entry point
```

### Dependency Management

- **Root `pyproject.toml`**: Defines shared linting rules and dev dependencies (pytest, ruff, yapf, vale)
- **Component `pyproject.toml`**: Each example/package/industry has its own dependencies
- **Version constraints**: Use at least 2-digit precision (e.g., `nvidia-nat~=1.2`, not `nvidia-nat==1`)
- **Local package dependencies**: Industries can reference packages via `[tool.uv.sources]`:

```toml
[tool.uv.sources]
nat_vanna_tool = { path = "../../packages/nat_vanna_tool", editable = true }

dependencies = [
  "nvidia-nat>=1.3.0",
  "nat_vanna_tool",  # References local package
]
```

### Multi-Framework Support

Components can support multiple AI frameworks via `framework_wrappers`:

```python
from nat.builder.builder import LLMFrameworkEnum

@register_function(
    config_type=MyToolConfig,
    framework_wrappers=[LLMFrameworkEnum.LANGCHAIN]
)
async def my_tool(config: MyToolConfig, builder: Builder):
    # Get LangChain-wrapped embedder
    embedder = await builder.get_embedder(
        config.embedder_name,
        wrapper_type=LLMFrameworkEnum.LANGCHAIN
    )
```

## Common Development Tasks

### Running NAT Workflows

```bash
# Run a workflow with a config file
nat run --config_file examples/mcp_rag_demo/configs/support-ui.yml --input "your query"

# Start an MCP server
nat mcp serve --config_file examples/mcp_rag_demo/configs/support-ui.yml --port 9904

# Start a UI server
nat serve --config_file examples/mcp_rag_demo/configs/mcp-client-for-ui.yml --port 8000
```

### Adding a New Example

1. Generate the structure: `nat workflow create`
2. Add dependencies to `pyproject.toml` with version constraints
3. Define config schema in `src/nat_$NAME/config_schemas.py`
4. Implement the function with `@register_function` decorator
5. Import the function in `register.py`
6. Add entry point to `pyproject.toml`
7. Create config files in `configs/`
8. Write tests in `tests/` using pytest
9. Document in README.md using `examples/.template/README.md` as a starting point

### Creating a Reusable Package

1. Create in `packages/nat_$NAME/`
2. Follow the same pattern as examples, but focus on reusability
3. Support optional dependencies via `[project.optional-dependencies]`
4. Document all configuration options in README.md
5. Examples and industries can then reference it via `[tool.uv.sources]`

### Working with Existing Components

When modifying existing examples/packages:
- Read the component's README.md first
- Check `pyproject.toml` for dependencies and entry points
- Look at `register.py` to see what functions are registered
- Review config files in `configs/` to understand usage
- Run tests after changes: `pytest path/to/component/tests/`

## Important Notes

### Git Commit Signing

**All commits to this repository must be signed with GPG.**

```bash
# Create a commit with GPG signature
git commit -S -m "Your commit message"

# Amend the last commit to add a signature
git commit --amend -S --no-edit

# Configure Git to always sign commits
git config --global commit.gpgsign true
```

When creating commits, always include:
- Clear, descriptive commit message
- Co-authored-by line: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>` when working with Claude

### Code Style

- All Python code must be compatible with ruff linting rules defined in root `pyproject.toml`
- Maximum line length: 120 characters
- Use isort for import organization (ruff handles this)
- Known first-party packages: `aiq`, `nat`, `nat_*`, `_utils`
- Known third-party packages: `agno`, `crewai`, `langchain`, `llama_index`, `mem0ai`, `redis`, `semantic_kernel`, `zep_cloud`

### Licensing

- All contributions must be Apache 2.0 licensed
- All files must include the SPDX copyright header (checked by CI)
- All dependencies must have Apache 2.0 compatible licenses

### Security

- Input validation is critical for tools that interact with databases or external systems
- Use whitelisting for categories, priorities, and other enum-like inputs (see `query_by_category_tool` in mcp_rag_demo for an example)
- Never include API keys or credentials in code or config files - use environment variables

### Documentation Requirements

Each component must include:
- Description of what the component does
- Key features
- Setup instructions
- How to run the component
- Expected results
- Troubleshooting tips (optional but recommended)
