<!--
SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# AIDP Retrieval API Demo with NVIDIA NIMs

## Overview

### The Problem

Enterprise AI applications need a standardized way to access enterprise data stored in storage platforms. Without a unified interface:

- **Custom integrations** - Each AI agent requires custom code to access storage
- **Inconsistent APIs** - Different storage vendors expose different interfaces
- **Tool fragmentation** - Tools built for one platform don't work with others
- **Security complexity** - Each integration needs its own authentication handling

### The Solution

This demo implements the **NVIDIA AI Data Platform (AIDP) Retrieval API** following the [OpenAI Vector Store Search specification](https://platform.openai.com/docs/api-reference/vector_stores/search). By exposing the Retrieval API via **Model Context Protocol (MCP)**, any MCP-compatible AI agent can seamlessly search enterprise data with a standardized interface.

### How It Works

The demo implements an **Agentic RAG (Retrieval-Augmented Generation)** system for searching support tickets:

1. **User asks a question** via the chat UI or CLI (for example, "Find GPU memory issues")
2. **ReAct Agent reasons** about which tools to use
3. **MCP Tool executes** - `search_vector_store` performs semantic search
4. **NVIDIA NIMs process** the request using GPU-accelerated embeddings
5. **Agent synthesizes** the results into a coherent response

### Component Selection

| Component | Technology | Why This Choice |
|-----------|------------|-----------------|
| **Protocol** | MCP (`Streamable HTTP`) | Open standard with auth support, works with any MCP client |
| **Agent Framework** | NeMo Agent Toolkit | Native MCP server/client, YAML config, production-ready |
| **Vector Database** | Milvus | GPU-accelerated, scales to billions of vectors |
| **Embeddings** | `nvidia/nv-embedqa-e5-v5` | High-quality 1024-dim embeddings optimized for Q&A retrieval |
| **LLM** | `meta/llama-3.1-70b-instruct` | Strong reasoning for agent orchestration and response generation |
| **API Spec** | OpenAI Vector Store Search | Industry standard for AI platform APIs |

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Running the Demo](#running-the-demo)
- [NVIDIA NIMs Used](#nvidia-nims-used)
- [The Tool](#the-tool)
- [Sample Queries](#sample-queries)
- [OpenAI API Alignment](#openai-api-alignment)
- [Customization Guide](#customization-guide)

---

## Key Features

- **OpenAI-Compatible API**: Implements the OpenAI Vector Store Search specification
- **MCP Protocol**: Tools exposed via standardized Model Context Protocol for interoperability
- **NVIDIA NIMs Integration**: Uses NVIDIA NIMs for embedding and LLM reasoning
- **Agentic RAG**: ReAct agent orchestrating search operations with tool calling
- **Vector Search**: Semantic similarity search using Milvus vector database
- **YAML-based Configuration**: Fully configurable workflow through YAML files

---

## Architecture

This demo uses a 3-terminal architecture:

1. **AIDP MCP Server** (`python src/nat_aidp_openai_demo/server.py`): Exposes `search_vector_store` via MCP
2. **NAT UI Server** (`nat serve`): Acts as MCP client, provides API for the UI
3. **NAT UI**: Frontend that users interact with

```
┌─────────────┐         REST          ┌─────────────────┐
│   NAT UI    │ ◄──────────────────►  │  NAT UI Server  │
│  (Browser)  │       Port 3000       │  (MCP Client)   │
└─────────────┘                       └────────┬────────┘
                                               │  Port 8000
                                        MCP Protocol
                                      (Streamable-HTTP)
                                               │
                                      ┌────────▼────────┐
                                      │  AIDP MCP Server│
                                      │   Port 8081     │
                                      │ search_vector_  │
                                      │     store       │
                                      └────────┬────────┘
                                               │
                              ┌────────────────┼────────────────┐
                              │                │                │
                      ┌───────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
                      │ Embedding NIM│  │   LLM NIM   │  │   Milvus    │
                      │  (API.NVIDIA)│  │ (API.NVIDIA)│  │ Port 19530  │
                      └──────────────┘  └─────────────┘  └─────────────┘
```

---

## Prerequisites

- Docker (for Milvus vector database)
- Python 3.11+
- NVIDIA API key from [build.nvidia.com](https://build.nvidia.com)
- Node.js (for UI)

---

## Installation and Setup

### Set Up API Keys

```bash
export NVIDIA_API_KEY=<YOUR_API_KEY>
```

### Start Milvus Vector Database

```bash
# Download the Milvus standalone docker-compose file
curl -sfL https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml -o docker-compose.yml

# Start Milvus
docker compose up -d
```

### Load Sample Data

```bash
python scripts/load_support_tickets.py
```

Expected output:
```
Creating collection: support_tickets with explicit schema
Collection 'support_tickets' created successfully
Inserted 10 tickets with NIM embeddings
Test search for 'GPU memory' returned 3 results
```

---

## Running the Demo

### Terminal 1: Start AIDP MCP Server

```bash
export NVIDIA_API_KEY=<YOUR_API_KEY>
python src/nat_aidp_openai_demo/server.py
```

### Terminal 2: Start NAT UI Server

```bash
export NVIDIA_API_KEY=<YOUR_API_KEY>
nat serve --config_file src/nat_aidp_openai_demo/configs/workflow.yml --port 8000
```

### Terminal 3: Start UI

```bash
cd external/nat-ui
npm run dev
```

### Open Browser

Navigate to: http://localhost:3000

**Alternative: Command Line**

```bash
nat run --config_file src/nat_aidp_openai_demo/configs/workflow.yml --input "Find GPU memory issues"
```

---

## NVIDIA NIMs Used

| NIM | Purpose | Model |
|-----|---------|-------|
| **Embedding** | Generate vector embeddings for semantic search | `nvidia/nv-embedqa-e5-v5` |
| **LLM** | Agent reasoning and response generation | `meta/llama-3.1-70b-instruct` |

---

## The Tool

### `search_vector_store`

Semantic search following the AIDP Retrieval API (OpenAI specification).

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `query` | string | Search query (required) | - |
| `vector_store_id` | string | Vector store name | `support_tickets` |
| `max_num_results` | integer | Results limit (1-50) | `10` |
| `filter_key` | string | Attribute to filter by | `null` |
| `filter_type` | string | Filter type: `eq`, `ne`, `contains` | `null` |
| `filter_value` | string | Value to match | `null` |
| `score_threshold` | float | Minimum similarity score | `null` |

---

## Sample Queries

Try these queries in the UI:

- "Find GPU memory issues"
- "Show me critical severity tickets"
- "What CUDA errors have been reported?"
- "Find driver crash issues"
- "Show resolved tickets about performance"

---

## OpenAI API Alignment

The AIDP Retrieval API follows the [OpenAI Vector Store Search specification](https://platform.openai.com/docs/api-reference/vector_stores/search):

### Endpoint

```
POST /v1/vector_stores/{vector_store_id}/search
```

### Response Format

```json
{
  "object": "vector_store.search_results.page",
  "search_query": "GPU memory issues",
  "data": [
    {
      "file_id": "d1649d77-e043-45e5-b426-9b8b7c2856f2",
      "filename": "CUDA out of memory error.txt",
      "score": 0.4976,
      "attributes": {
        "category": "Memory Problems",
        "severity": "high",
        "title": "CUDA out of memory error with large batch sizes"
      },
      "content": [
        {
          "type": "text",
          "text": "Training transformer model with batch size 64..."
        }
      ]
    }
  ],
  "has_more": false,
  "next_page": null
}
```

### Alignment Table

| OpenAI Spec | AIDP Implementation |
|-------------|---------------------|
| `query` (required) | ✅ Implemented |
| `filters` (key/type/value) | ✅ Implemented |
| `max_num_results` (1-50) | ✅ Implemented |
| `ranking_options` | ✅ Implemented |
| Response: `file_id`, `filename`, `score` | ✅ Identical |
| Response: `attributes`, `content[]` | ✅ Identical |
| Bearer token authentication | ✅ Implemented |

---

## Customization Guide

### Adding New Fields

1. Update the Milvus schema in `scripts/load_support_tickets.py`
2. Add the field to `output_fields` in `src/nat_aidp_openai_demo/server.py`
3. Include the field in the response `attributes` object

### Using Different Models

Update `src/nat_aidp_openai_demo/configs/workflow.yml`:

```yaml
llms:
  nim_llm:
    _type: nim
    model_name: meta/llama-3.3-70b-instruct  # Change model here
    temperature: 0
    max_tokens: 512
```

### Connecting to Different Vector Stores

Set the environment variable:

```bash
export MILVUS_URI="http://your-milvus-host:19530"
```

---

## Files

| File | Purpose |
|------|---------|
| `src/nat_aidp_openai_demo/server.py` | MCP server exposing `search_vector_store` tool |
| `src/nat_aidp_openai_demo/configs/workflow.yml` | NeMo Agent Toolkit workflow configuration |
| `scripts/load_support_tickets.py` | Data loading script for Milvus |

---

## References

- [OpenAI Vector Store Search API](https://platform.openai.com/docs/api-reference/vector_stores/search)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [NeMo Agent Toolkit](https://github.com/NVIDIA/NeMo-Agent-Toolkit)

