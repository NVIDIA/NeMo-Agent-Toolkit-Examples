# Support Tickets MCP Demo with NVIDIA NIMs

Demo showing how to expose tools via MCP protocol using NeMo Agent Toolkit with NVIDIA NIM integration.

## Quick Start

### Prerequisites
- Docker (for Milvus)
- Python 3.11+
- NVIDIA API key from build.nvidia.com
- Node.js (for UI)

### 1. Start Milvus
```bash
cd ~/milvus_setup
docker-compose up -d
```

### 2. Load Data
```bash
cd ~/natreal/NeMo-Agent-Toolkit
source .venv311/bin/activate
export NVIDIA_API_KEY="your-nvidia-api-key-here"
python examples/mcp_rag_demo/scripts/load_support_tickets.py
```

### 3. Start NAT MCP Server (Terminal 1)
```bash
export NVIDIA_API_KEY="your-nvidia-api-key-here"
nat mcp serve --config_file examples/mcp_rag_demo/configs/support-ui.yml --port 9904
```

### 4. Start NAT UI Server (Terminal 2)
```bash
export NVIDIA_API_KEY="your-nvidia-api-key-here"
nat serve --config_file examples/mcp_rag_demo/configs/mcp-client-for-ui.yml --port 8000
```

### 5. Start UI (Terminal 3)
```bash
cd external/nat-ui
export NAT_BACKEND_URL="http://localhost:8000"
npm run dev
```

### 6. Open Browser
http://localhost:8000

## What This Demonstrates

- **MCP Protocol**: Tools exposed via standardized MCP protocol
- **NVIDIA NIMs**: Embedding and reranking models
- **Agentic RAG**: ReAct agent orchestrating search operations
- **4 Tools**: semantic search, category filter, priority filter, reranking
