<!--
SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# NeMo Agent Toolkit Profiler Agent

**Complexity:** 🟨 Intermediate

The profiler agent is a tool that allows you to analyze the performance of NeMo Agent Toolkit workflows. It uses the Phoenix server to store and retrieve traces of workflow runs.

> [!NOTE]
> This example is a snapshot copy from `NVIDIA/NeMo-Agent-Toolkit` commit `c402fd35b73145e90db03c040d1aa652fbe7c32b`.

## Table of Contents

- [NeMo Agent Toolkit Profiler Agent](#nemo-agent-toolkit-profiler-agent)
  - [Table of Contents](#table-of-contents)
  - [Key Features](#key-features)
  - [Installation and Setup](#installation-and-setup)
    - [Install this Workflow:](#install-this-workflow)
    - [Set Up API Keys](#set-up-api-keys)
  - [Run the Workflow](#run-the-workflow)
  - [Features](#features)

## Key Features

- **Workflow Performance Analysis:** Demonstrates a specialized agent that analyzes NeMo Agent Toolkit workflow performance using Phoenix server traces for comprehensive performance monitoring.
- **Token Usage Tracking:** Shows how to retrieve and analyze token consumption patterns across multiple workflow runs, providing insights into LLM resource utilization.
- **Trace Visualization:** Generates flowcharts and visual representations of workflow execution patterns from stored Phoenix traces using natural language queries.
- **Phoenix Server Integration:** Demonstrates integration with Phoenix observability platform for storing, retrieving, and analyzing workflow telemetry data.
- **Natural Language Interface:** Provides a conversational interface for querying performance metrics, making complex trace analysis accessible through simple questions.

## Installation and Setup

If you have not already done so, follow the NeMo Agent Toolkit installation guide:
https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/main/docs/source/get-started/installation.md

### Install this Workflow:

From the root directory of the NeMo Agent Toolkit Examples repository, run:

```bash
uv pip install --prerelease=allow -e examples/profiler_agent
```

### Set Up API Keys
If you have not already done so, follow the API key instructions:
https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/main/docs/source/get-started/quick-start.md#obtaining-api-keys

```bash
export NVIDIA_API_KEY=<YOUR_API_KEY>
```

## Run the Workflow

1. Start the Phoenix server if not already running. If you are using a remote Phoenix server, you can skip this step and modify the configs/config.yml file to point to the URL.
   ```bash
   docker run -p 6006:6006 -p 4317:4317 -i -t arizephoenix/phoenix:latest
   ```

2. Ensure that there are traces in the Phoenix server. You can use any workflow instrumented with Phoenix telemetry to generate traces.
   > [!NOTE]
   Then, run an instrumented workflow to generate traces.
   ```bash
   # Example placeholder:
   # nat run --config_file <your-phoenix-enabled-config.yml> --input "<your test prompt>"
   ```

3. Run the profiler agent:
   ```
   nat serve --config_file=examples/profiler_agent/configs/config.yml
   ```

4. Launch the NeMo Agent Toolkit UI by following:
   https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/main/docs/source/run-workflows/launching-ui.md

5. Query the agent with natural language via the UI:
   ```
   Show me the token usage of last run
   ```

   ```
   Show me flowchart of last 3 runs
   ```

   ```
   Analyze the last 2 runs
   ```

## Features

- Query Phoenix traces with natural language
- Analyze LLM application performance metrics
- Generate trace visualizations
- Extract user queries across trace spans
