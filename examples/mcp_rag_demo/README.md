<!--
SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# MCP RAG Demo with NVIDIA NIMs

## Overview

### The Problem

Enterprise AI applications need to connect Large Language Models (LLMs) to external data sources and tools. However, each integration typically requires custom code, leading to:

- **Fragmented tool ecosystems** - Different frameworks require different integration patterns
- **Vendor lock-in** - Tools built for one AI platform don't work with others
- **Security complexity** - Each integration needs its own authentication handling
- **Maintenance burden** - Updates to tools require changes across multiple integrations

### The Solution

This example demonstrates how to solve these challenges using the **Model Context Protocol (MCP)** - an open standard that enables AI applications to securely connect to external tools through a unified interface. By exposing tools via MCP, they become instantly accessible to any MCP-compatible client including Claude Desktop, Cursor IDE, and custom agents.

### How It Works

The demo implements an **Agentic RAG (Retrieval-Augmented Generation)** system for searching support tickets:

1. **User asks a question** via the chat UI (e.g., "Find critical GPU driver issues")
2. **ReAct Agent reasons** about which tools to use and in what order
3. **MCP Tools execute** - semantic search, filtering, and reranking operations
4. **NVIDIA NIMs process** the requests using GPU-accelerated AI models
5. **Agent synthesizes** the results into a coherent response

### Component Selection

| Component | Technology | Why This Choice |
|-----------|------------|-----------------|
| **Protocol** | MCP (`Streamable HTTP`) | Open standard with auth support, works with any MCP client |
| **Agent Framework** | NeMo Agent Toolkit | Native MCP server/client, YAML config, production-ready |
| **Vector Database** | Milvus | GPU-accelerated with cuVS, scales to billions of vectors |
| **Embeddings** | `nvidia/nv-embedqa-e5-v5` | High-quality 1024-dim embeddings optimized for Q&A retrieval |
| **LLM** | `meta/llama-3.1-70b-instruct` | Strong reasoning for agent orchestration and response generation |
| **Reranker** | `nvidia/llama-3.2-nv-rerankqa-1b-v2` | Improves retrieval precision by reordering results by relevance |

---

## Table of Contents

- [MCP RAG Demo with NVIDIA NIMs](#mcp-rag-demo-with-nvidia-nims)
  - [Overview](#overview)
    - [The Problem](#the-problem)
    - [The Solution](#the-solution)
    - [How It Works](#how-it-works)
    - [Component Selection](#component-selection)
  - [Table of Contents](#table-of-contents)
  - [Key Features](#key-features)
  - [Architecture](#architecture)
  - [Prerequisites](#prerequisites)
  - [Installation and Setup](#installation-and-setup)
    - [Install this Workflow](#install-this-workflow)
    - [Set Up API Keys](#set-up-api-keys)
    - [Start Milvus Vector Database](#start-milvus-vector-database)
    - [Load Sample Data](#load-sample-data)
  - [Running the Demo](#running-the-demo)
    - [Terminal 1: Start NAT MCP Server](#terminal-1-start-nat-mcp-server)
    - [Terminal 2: Start NAT UI Server](#terminal-2-start-nat-ui-server)
    - [Terminal 3: Start UI](#terminal-3-start-ui)
    - [Open Browser](#open-browser)
  - [NVIDIA NIMs Used](#nvidia-nims-used)
  - [The 4 Tools](#the-4-tools)
  - [Sample Queries](#sample-queries)
  - [Customization Guide](#customization-guide)
    - [Adding New Functions](#adding-new-functions)
    - [Modifying the Agent](#modifying-the-agent)
    - [Using Different Models](#using-different-models)

---

## Key Features

- **MCP Protocol**: Tools exposed via standardized Model Context Protocol for interoperability
- **NVIDIA NIMs Integration**: Uses NVIDIA NIMs for embedding, LLM reasoning, and reranking
- **Custom Functions**: 4 tools registered via `@register_function` decorator
- **Agentic RAG**: ReAct agent orchestrating search operations with tool calling
- **Vector Search**: Semantic similarity search using Milvus vector database
- **YAML-based Configuration**: Fully configurable workflow through YAML files

---

## Architecture

This demo uses a 3-terminal architecture:

1. **NAT MCP Server** (`nat mcp serve`): Exposes the 4 custom tools via MCP protocol
2. **NAT UI Server** (`nat serve`): Acts as MCP client, provides API for the UI
3. **NAT UI**: Frontend that users interact with

```
┌─────────────┐         REST          ┌─────────────────┐
│   NAT UI    │ ◄──────────────────►  │  NAT UI Server  │
│  (Browser)  │                       │  (MCP Client)   │
└─────────────┘                       └────────┬────────┘
                                               │
                                        MCP Protocol
                                      (Streamable-HTTP)
                                               │
                                      ┌────────▼────────┐
                                      │  NAT MCP Server │
                                      │  (Tool Server)  │
                                      └────────┬────────┘
                                               │
                              ┌────────────────┼────────────────┐
                              │                │                │
                      ┌───────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
                      │ Embedding NIM│  │   LLM NIM   │  │ Rerank NIM  │
                      └──────────────┘  └─────────────┘  └─────────────┘
```

---

## Prerequisites

- Docker (for Milvus vector database)
- Python 3.11+
- NVIDIA API key
- Node.js (for UI)

---

## Installation and Setup

### Install this Workflow

From the root directory of the NeMo Agent Toolkit Examples repository, run:

```bash
uv pip install --prerelease=allow -e examples/mcp_rag_demo
```

### Set Up API Keys

```bash
export NVIDIA_API_KEY=<YOUR_API_KEY>
```

### Start Milvus Vector Database

```bash
# If you don't have Milvus set up, create a docker-compose.yml:
mkdir -p ~/milvus_setup && cd ~/milvus_setup

# Download the Milvus standalone docker-compose file
wget https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml -O docker-compose.yml

# Start Milvus
docker-compose up -d
```

### Load Sample Data
**Note:** The sample dataset is synthetic. To use your own data, modify `load_support_tickets.py` with your Milvus connection and data schema, then update the tool queries in `register.py` to match your fields.

```bash
python examples/mcp_rag_demo/scripts/load_support_tickets.py
```

Expected output:
```
✓ Connected to Milvus
✓ Created support_tickets collection
✓ Prepared 15 support tickets
✓ Calling NVIDIA NIM API to generate embeddings...
✓ Generated 15 embeddings using NVIDIA NIM (`nvidia/nv-embedqa-e5-v5`)
✓ Inserted 15 tickets into Milvus
✓ Created vector index
✓ Loaded collection into memory
============================================================
Successfully loaded 15 support tickets into Milvus
Collection: support_tickets
============================================================
```

---

## Running the Demo

### Terminal 1: Start NAT MCP Server

```bash
export NVIDIA_API_KEY=<YOUR_API_KEY>
nat mcp serve --config_file examples/mcp_rag_demo/configs/support-ui.yml --port 9904
```

### Terminal 2: Start NAT UI Server

```bash
export NVIDIA_API_KEY=<YOUR_API_KEY>
nat serve --config_file examples/mcp_rag_demo/configs/mcp-client-for-ui.yml --port 8000
```

### Terminal 3: Start UI

```bash
cd external/nat-ui
export NAT_BACKEND_URL="http://localhost:8000"
npm run dev
```

### Open Browser

Navigate to: http://localhost:3000

---

## NVIDIA NIMs Used

| NIM | Purpose | Model |
|-----|---------|-------|
| **Embedding** | Generate vector embeddings for semantic search | `nvidia/nv-embedqa-e5-v5` |
| **LLM** | Agent reasoning and response generation | `meta/llama-3.1-70b-instruct` |
| **Reranking** | Improve search relevance | `nvidia/llama-3.2-nv-rerankqa-1b-v2` |

---

## The 4 Tools

1. `search_support_tickets`: Semantic search using NIM embeddings
2. `query_by_category`: Filter tickets by category e.g. `bug_report`, `feature_request`, `question`, `incident`
3. `query_by_priority`: Filter tickets by priority (critical, high, medium, low)
4. `rerank_support_tickets`: Rerank results using NIM reranker for improved relevance

---

## Sample Queries

Try these queries in the UI:

- "Find tickets about GPU driver crashes"
- "Show me critical incidents"
- "What bugs are related to CUDA?"
- "Find feature requests for the API"
- "Show me resolved Milvus performance issues"

---

## Customization Guide

### Adding New Functions

1. Define a new config class in `register.py` that inherits from `FunctionBaseConfig`
2. Create a function decorated with `@register_function`
3. Add the function to your `support-ui.yml` config file
4. Update the workflow's `tool_names` list

### Modifying the Agent

- Change the `_type` in the workflow section to use different agent types
- Adjust `max_iterations`, `temperature`, or other parameters as needed
- Add custom system prompts or modify the agent behavior

### Using Different Models

- Update the `model_name` in the LLM configuration
- Adjust parameters such as `temperature` and `max_tokens`
- Switch between different LLM providers (OpenAI, NIM, and so on)
