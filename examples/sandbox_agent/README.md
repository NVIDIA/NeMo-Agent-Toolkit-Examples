<!--
SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Sandbox Agent

A general-purpose AI agent with sandboxed code execution for the NVIDIA NeMo Agent Toolkit (NAT).

## Overview

The Sandbox Agent executes tasks within secure, isolated Docker containers or Daytona cloud sandboxes. All code, commands, and file operations run in complete isolation from the host system.

**Key Capabilities:**
- Execute shell commands and Python code in isolated containers
- Browse websites and extract content
- Search the web using Tavily AI Search
- Read and write files within the sandbox
- Extract transcripts from YouTube videos

## Quick Start

### Prerequisites

- Docker (running daemon)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- API keys (see Environment Variables below)

### Installation

```bash
cd examples/sandbox_agent

# Install package
uv pip install -e . --prerelease=allow

# Build sandbox Docker image
docker build -t nat-sandbox:latest .
```

### Environment Variables

```bash
# Required: LLM access
export NVIDIA_API_KEY="your-nvidia-api-key"

# Required: Web search
export TAVILY_API_KEY="your-tavily-api-key"  # Free at https://tavily.com

# Optional: OpenAI models
export OPENAI_API_KEY="your-openai-api-key"

# Optional: Daytona cloud sandboxes
export DAYTONA_API_KEY="your-daytona-api-key"
```

### Run the Agent

```bash
nat run --config_file configs/config.yaml --input "Write a Python program to print the first ten Fibonacci numbers."
```

## Available Tools

| Tool | Location | Description |
|------|----------|-------------|
| `shell` | Sandbox | Execute bash commands (file management, git, curl, etc.) |
| `python` | Sandbox | Execute Python code (data analysis, calculations, API calls) |
| `file_read` | Sandbox | Read file contents |
| `file_write` | Sandbox | Write content to files |
| `web_browse` | Sandbox | Navigate URLs and extract page content |
| `web_search` | Host | Search the web via Tavily API |
| `youtube_transcript` | Host | Extract transcripts from YouTube videos |

**Sandbox tools** run inside the Docker container with access to `/workspace`.
**Host tools** run on the host machine (API keys stay secure).

## Configuration

### Basic Configuration

```yaml
# configs/config.yaml
llms:
  agent_llm:
    _type: nim
    model_name: meta/llama-3.3-70b-instruct
    temperature: 0.0

workflow:
  _type: sandbox_agent
  llm_name: agent_llm
  max_iterations: 20
  sandbox_config:
    type: docker
    image: "nat-sandbox:latest"
    memory_limit: "1g"
    cpu_limit: 2.0
    network_enabled: true
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `max_iterations` | 20 | Maximum agent reasoning steps |
| `max_observation_tokens` | 10000 | Token limit for tool outputs |
| `sandbox_config.type` | docker | Sandbox type: `docker` or `daytona` |
| `sandbox_config.image` | python:3.12-slim | Docker image to use |
| `sandbox_config.memory_limit` | 512m | Container memory limit |
| `sandbox_config.cpu_limit` | 1.0 | CPU cores allocated |
| `sandbox_config.network_enabled` | true | Allow network access |
| `sandbox_config.volumes` | {} | Host directories to mount (Docker only) |
| `sandbox_config.environment` | {} | Environment variables to pass |
| `enabled_tools` | null | List of tools to enable (null = all) |
| `sandbox_config.auto_stop_interval` | 30 | Auto-stop interval in minutes (Daytona only) |

### Using OpenAI Models

```yaml
llms:
  agent_llm:
    _type: openai
    model_name: gpt-4o
    temperature: 0.0
```

### Using Daytona Cloud

Daytona provides cloud-based sandboxes as an alternative to local Docker containers.

**Requirements:**
- Install Daytona SDK: `uv pip install daytona-sdk`
- Set `DAYTONA_API_KEY` environment variable

**Configuration:**
```yaml
workflow:
  _type: sandbox_agent
  sandbox_config:
    type: daytona
    api_key: ${DAYTONA_API_KEY}
    image: "python:3.12-slim"
    cpu: 2
    memory: 4   # GB (max 8)
    disk: 10    # GB (max 10)
    auto_stop_interval: 30  # minutes
```

**Run with Daytona:**
```bash
nat run --config_file configs/config_daytona.yaml --input "Your task here"
```

**Limitations:**
- Daytona sandboxes cannot mount local volumes, so file-based tasks (like GAIA with attachments) may have reduced functionality
- Resource limits are lower than Docker (max 10GB disk, 8GB memory)

## Sandbox Environment

The sandbox provides an isolated workspace:

```
/workspace/
├── input/      # Input files (mounted or uploaded)
├── output/     # Generated outputs
├── temp/       # Temporary files
└── downloads/  # Downloaded files
```

**Pre-installed in nat-sandbox image:**
- Data processing: pandas, numpy, matplotlib, seaborn
- Web: requests, httpx, beautifulsoup4
- Browser: playwright (Chromium)
- Documents: python-pptx, python-docx, reportlab
- Utilities: pillow, pyyaml, openpyxl

## GAIA Benchmark Evaluation

The Sandbox Agent is configured for [GAIA benchmark](https://huggingface.co/datasets/gaia-benchmark/GAIA) evaluation.

### Setup

1. **Accept the GAIA license** at https://huggingface.co/datasets/gaia-benchmark/GAIA

2. **Download GAIA attachments** (required for file-based tasks):
   ```bash
   hf download gaia-benchmark/GAIA --repo-type dataset \
     --include "2023/validation/*" --local-dir /tmp/gaia && \
     mv /tmp/gaia/2023/validation/* data/attachments/
   ```

3. **Run evaluation:**
   ```bash
   # Level 2 (default)
   GAIA_ATTACHMENTS_DIR=$(pwd)/data/attachments nat eval --config_file configs/config_gaia.yaml

   # Specific level
   GAIA_LEVEL=1 GAIA_ATTACHMENTS_DIR=$(pwd)/data/attachments nat eval --config_file configs/config_gaia.yaml

   # With different LLM
   LLM_TYPE=openai LLM_MODEL=gpt-4o GAIA_ATTACHMENTS_DIR=$(pwd)/data/attachments nat eval --config_file configs/config_gaia.yaml
   ```

### Evaluation Metrics

- **Accuracy**: Answer correctness (RAGAS metric)
- **Runtime**: Average task execution time
- **LLM Latency**: Average LLM response time
- **LLM Calls**: Average number of LLM calls per task

### Results (January 2026)

**GPT-5.2:**

| Level | Tasks | Accuracy | Description |
|-------|-------|----------|-------------|
| Level 1 | 53 | **55.66%** | Basic tasks |
| Level 2 | 86 | **51.16%** | Intermediate tasks |
| Level 3 | 26 | **36.54%** | Complex tasks |

**NIM LLaMA-3.3-70B**:

| Level | Tasks | Accuracy | Description |
|-------|-------|----------|-------------|
| Level 1 | 53 | **33.49%** | Basic tasks |
| Level 2 | 86 | **18.02%** | Intermediate tasks |
| Level 3 | 26 | **11.54%** | Complex tasks |

*Results depend on model capabilities, sandbox resources, and task types.*

## Project Structure

```
sandbox_agent/
├── README.md
├── Dockerfile                    # Sandbox image definition
├── pyproject.toml               # Dependencies
├── configs -> src/.../configs   # Symlink to configs
├── data -> src/.../data         # Symlink to data
│
├── src/nat_sandbox_agent/
│   ├── register.py              # Workflow registration
│   │
│   ├── sandbox/                 # Sandbox implementations
│   │   ├── base.py              # BaseSandbox abstract class
│   │   ├── docker_sandbox.py    # Docker implementation
│   │   ├── daytona_sandbox.py   # Daytona cloud implementation
│   │   └── factory.py           # Sandbox factory
│   │
│   ├── tools/                   # Tool system
│   │   ├── factory.py           # Tool factory
│   │   ├── sandbox/             # Sandbox-side tools
│   │   │   ├── executor.py      # Base executor
│   │   │   ├── execution.py     # shell, python
│   │   │   ├── file_ops.py      # file_read, file_write
│   │   │   └── browser.py       # web_browse
│   │   └── host/                # Host-side tools
│   │       ├── web_search.py    # web_search
│   │       └── youtube.py       # youtube_transcript
│   │
│   ├── prompts/                 # System prompts
│   │   └── system_prompt.py
│   │
│   ├── configs/                 # YAML configurations
│   │   ├── config.yaml          # Basic setup
│   │   ├── config_daytona.yaml  # Daytona cloud
│   │   ├── config_gaia.yaml     # GAIA evaluation (Docker)
│   │   └── config_daytona_gaia.yaml  # GAIA evaluation (Daytona)
│   │
│   ├── utils/                   # Utilities
│   │   └── answer_cleaning.py   # Answer post-processing
│   │
│   └── data/
│       └── attachments/         # GAIA attachments (not in repo)
│
└── tests/                       # Unit tests
```

## Development

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Skip Docker integration tests
pytest tests/ -v -m "not integration"

# With coverage
pytest tests/ --cov=nat_sandbox_agent
```

### Building the Sandbox Image

```bash
# Build
docker build -t nat-sandbox:latest .

# Test
docker run -it --rm nat-sandbox:latest python -c "import pandas; print('OK')"
```

## Troubleshooting

**Docker permission denied:**
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

**Tavily API not working:**
- Verify `TAVILY_API_KEY` is set
- Check API key at https://app.tavily.com

**GAIA evaluation fails with missing files:**
- Download attachments from HuggingFace (see GAIA Setup above)
- Verify files exist in `data/attachments/`

**Out of memory:**
- Increase `memory_limit` in sandbox config
- Use `nat-sandbox:latest` image (optimized)

**Daytona sandbox issues:**
- Verify `DAYTONA_API_KEY` is set and valid
- Check resource limits (max 10GB disk, 8GB memory)
- Ensure `daytona-sdk` is installed: `uv pip install daytona-sdk`
- Note: Daytona cannot mount local volumes; file-based tasks may fail

## License

Apache 2.0 - See LICENSE file for details.
