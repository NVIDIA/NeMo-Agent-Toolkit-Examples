<!--
SPDX-FileCopyrightText: Copyright (c) 2024-2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# NV-Ingest MCP RAG Example

This example demonstrates how to use NVIDIA NeMo Agent toolkit with NV-Ingest for document processing and retrieval workflows. You can expose NV-Ingest capabilities as MCP tools for AI agents to ingest documents, build knowledge bases, and perform semantic search.

## Prerequisites

1. **NeMo Agent Toolkit**: Ensure you have the NeMo Agent toolkit installed. If you have not already done so, follow the instructions in the [NeMo Agent Toolkit documentation](https://github.com/NVIDIA/NeMo-Agent-Toolkit) to create the development environment and install NeMo Agent Toolkit.

2. **NV-Ingest Stack**: This example assumes you have NV-Ingest (NeMo Retriever Extraction) deployed locally. Your NV-Ingest services must be running:
   - NV-Ingest microservice on port 7670
   - Milvus on port 19530
   - Embedding service on port 8012
   - MinIO on port 9000

   If you don't have NV-Ingest deployed, refer to the [NV-Ingest documentation](https://github.com/NVIDIA/nv-ingest/blob/main/README.md) for setup instructions. For quick testing, you can use [Library Mode](https://github.com/NVIDIA/nv-ingest/blob/main/README.md#library-mode-quickstart) which requires only self-hosted NIMs or NIMs hosted on build.nvidia.com.

3. **API Key**: Set your NVIDIA API key:
   ```bash
   export NVIDIA_API_KEY=<your_key>
   ```

   If you don't have an API key, you can get one from [build.nvidia.com](https://org.ngc.nvidia.com/setup/api-keys).

**Note**: If you installed NeMo Agent toolkit from source, MCP client functionality is already included. If you installed from PyPI, you may need to install the MCP dependencies separately with `uv pip install "nvidia-nat[mcp,langchain]"`.

## Install this Workflow

Install this example:

```bash
uv pip install -e examples/nvingest_mcp
```

## Run the Workflow

This example includes sample PDF files in `data/` for testing.

**Note:** This is a simple example demonstrating end-to-end functionality. The tool implementations in `src/` are intentionally basic to illustrate the concepts. For production use cases, you may want to extend the retrieval logic with filtering, reranking, or more sophisticated chunking strategies.

This example supports three modes of operation:

| Mode | When to Use |
|------|-------------|
| **Mode 1: Direct Agent** | Uses `nat run` with tools defined in YAML - fastest and simplest |
| **Mode 2: MCP Server** | Expose tools for Cursor, Claude Desktop, or other MCP-compatible apps |
| **Mode 3: MCP Client** | Your NAT agent uses tools from an external MCP server (different tools or different machine) |

### Mode 1: Direct Agent (Simplest)

Tools defined directly in YAML configuration. Lowest latency, single process.

#### Example Queries

```bash
# Ingest the sample document
nat run --config_file examples/nvingest_mcp/configs/nvingest_agent_direct.yml \
    --input "Ingest examples/nvingest_mcp/data/multimodal_test.pdf into the vector database"
```

**Expected output:** The pipeline extracts text, tables, and charts from the PDF, generates embeddings, and uploads 8 chunks to Milvus collection `nv_ingest_collection`.

```bash
# Search the knowledge base
nat run --config_file examples/nvingest_mcp/configs/nvingest_agent_direct.yml \
    --input "Search for information about tables and charts"
```

**Expected output:** Returns information about charts showing average frequency ranges for speaker drivers and tables describing animals and their activities. To verify the extracted content, view the source document: [multimodal_test.pdf](data/multimodal_test.pdf).

```bash
# Ask questions about the ingested documents
nat run --config_file examples/nvingest_mcp/configs/nvingest_agent_direct.yml \
    --input "What animals are mentioned in the documents?"
```

**Expected output:** The animals mentioned in the documents are Giraffe, Lion, Cat, and Dog.

### Mode 2: MCP Server

Expose tools as MCP endpoints for external clients.

#### Start the Server

```bash
nat mcp serve \
    --config_file examples/nvingest_mcp/configs/nvingest_mcp_server.yml \
    --host 0.0.0.0 \
    --port 9901
```

Server will be available at: `http://localhost:9901/mcp`

#### Verify Server is Running

```bash
# Check health
curl http://localhost:9901/health

# List available tools
curl http://localhost:9901/debug/tools/list | jq

# Ping through MCP protocol
nat mcp client ping --url http://localhost:9901/mcp

# List tools through MCP protocol
nat mcp client tool list --url http://localhost:9901/mcp
```

#### Call Tools Directly (No LLM)

```bash
# Call document_ingest_vdb tool
nat mcp client tool call document_ingest_vdb \
    --url http://localhost:9901/mcp \
    --json-args '{"file_path": "examples/nvingest_mcp/data/embedded_table.pdf"}'
```

**Expected output:** 10 chunks uploaded to Milvus collection `nv_ingest_collection`.

```bash
# Call semantic_search tool (returns raw document chunks)
nat mcp client tool call semantic_search \
    --url http://localhost:9901/mcp \
    --json-args '{"query": "What is the minimum version of xlrd and what are the notes about it?"}'
```

**Expected output:** Returns raw document chunks containing the Excel dependencies table with xlrd version 2.0.1.

#### Call the Agent Workflow (With LLM Reasoning)

The `react_agent` workflow is also exposed as an MCP tool, allowing you to ask questions and get formulated answers:

```bash
# Ask a question and get a reasoned answer
nat mcp client tool call react_agent \
    --url http://localhost:9901/mcp \
    --json-args '{"query": "What is the minimum version of xlrd and what are the notes about it?"}'
```

**Expected output:** The minimum version of xlrd is 2.0.1, and the notes indicate it is used for "Reading Excel". To verify, see [embedded_table.pdf](data/embedded_table.pdf).

### Mode 3: MCP Client

Connect to the MCP server from another workflow.

#### Step 1: Start the MCP Server (Terminal 1)

```bash
nat mcp serve \
    --config_file examples/nvingest_mcp/configs/nvingest_mcp_server.yml \
    --host 0.0.0.0
```

#### Step 2: Run the MCP Client Workflow (Terminal 2)

```bash
# Set your API key first
export NVIDIA_API_KEY=<your_key>

# Ingest through MCP
nat run --config_file examples/nvingest_mcp/configs/nvingest_mcp_client.yml \
    --input "Ingest examples/nvingest_mcp/data/test-page-form.pdf into the database"
```

**Expected output:** 1 chunk uploaded to Milvus collection `nv_ingest_collection`.

```bash
# Search through MCP
nat run --config_file examples/nvingest_mcp/configs/nvingest_mcp_client.yml \
    --input "Search the knowledge base for information about Parallel Key-Value Cache Fusion and who are the authors"
```

**Expected output:** The authors of the paper "Parallel Key-Value Cache Fusion for Position Invariant RAG" are Philhoon Oh, Jinwoo Shin, and James Thorne from KAIST AI. To verify, see [test-page-form.pdf](data/test-page-form.pdf).

## Available Tools

### 1. `document_ingest` - Extract Content (No VDB)

Extracts content from documents and returns it directly. Use for inspection or custom processing.

**Input:**
- `file_path`: Path to the document (PDF, DOCX, and so on)

**Output:** Extracted text, tables, and charts as formatted string

### 2. `document_ingest_vdb` - Extract + Embed + Upload

Full pipeline: extracts content, generates embeddings, uploads to Milvus. Use to build your knowledge base.

**Input:**
- `file_path`: Path to the document

**Output:** Status message with chunk count and collection name

### 3. `semantic_search` - Query Knowledge Base

Searches Milvus for documents relevant to a natural language query.

**Input:**
- `query`: Natural language search query

**Output:** Top-K relevant document chunks

## Configuration

### Extraction Options

Configure what to extract from documents in your config YAML:

| Option | Description | NIM Service Used |
|--------|-------------|------------------|
| `extract_text` | Plain text content | Built-in |
| `extract_tables` | Structured table data | table-structure (port 8006) |
| `extract_charts` | Chart and graphic descriptions | graphic-elements (port 8003) |
| `extract_images` | Image content | page-elements (port 8000) |

Example configuration:

```yaml
document_ingest_vdb:
  extract_text: true
  extract_tables: true
  extract_charts: true
  extract_images: false
```

> **Note on Embedding URLs:** The configs use different embedding URLs because of Docker networking:
> - `document_ingest_vdb` uses `http://embedding:8000/v1` - NV-Ingest runs inside Docker and reaches the embedding service via Docker's internal network
> - `semantic_search` uses `http://localhost:8012/v1` - runs on the host machine and reaches the embedding service via the exposed port

### Configuration Reference

#### Direct Mode (`nvingest_agent_direct.yml`)

```yaml
functions:
  document_ingest_vdb:
    _type: nvingest_document_ingest_vdb
    nvingest_host: localhost
    nvingest_port: 7670
    milvus_uri: http://localhost:19530
    collection_name: nv_ingest_collection
    embedding_url: http://embedding:8000/v1  # Docker internal network
    embedding_model: nvidia/llama-3.2-nv-embedqa-1b-v2

  semantic_search:
    _type: milvus_semantic_search
    milvus_uri: http://localhost:19530
    embedding_url: http://localhost:8012/v1  # Host machine access
    embedding_model: nvidia/llama-3.2-nv-embedqa-1b-v2

workflow:
  _type: react_agent
  tool_names: [document_ingest, document_ingest_vdb, semantic_search]
  llm_name: nim_llm
```

#### MCP Client Mode (`nvingest_mcp_client.yml`)

```yaml
function_groups:
  nvingest_tools:
    _type: mcp_client
    server:
      transport: streamable-http
      url: "http://localhost:9901/mcp"
    include:
      - document_ingest_vdb
      - semantic_search

workflow:
  _type: react_agent
  tool_names: [nvingest_tools]
```

## Troubleshooting

Test your service connections:

```bash
# Test NV-Ingest connection
curl http://localhost:7670/health

# Test Milvus connection
curl http://localhost:19530/health

# Test embedding service
curl http://localhost:8012/v1/models

# Test MCP server (if running)
curl http://localhost:9901/health
```

## Capabilities

This integration enables AI agents to:

- **Ingest documents**: Process PDFs, extract text, tables, charts, and images
- **Build knowledge bases**: Automatically embed and store documents in Milvus VDB
- **Semantic search**: Query the knowledge base using natural language
- **Retrieval workflows**: Combine retrieval with LLM reasoning for document Q&A
