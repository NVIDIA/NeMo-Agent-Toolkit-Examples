# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3
"""
AIDP Retrieval API - MCP HTTP Server

This MCP server exposes the AIDP Retrieval API over HTTP using the
streamable-http transport, allowing NeMo Agent Toolkit to connect
as an MCP client.

Implements the OpenAI Vector Store Search specification:
    POST /v1/vector_stores/{vector_store_id}/search

MCP Tool: search_vector_store

Usage:
    python server.py
    
    Then configure NAT to connect:
    function_groups:
      aidp:
        _type: mcp_client
        server:
          transport: streamable-http
          url: "http://localhost:8081/mcp"
"""

import os
import json
import logging
from typing import Optional

from fastmcp import FastMCP

from pymilvus import MilvusClient
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aidp-mcp-http-server")

# Configuration
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
MCP_PORT = int(os.getenv("MCP_PORT", "8081"))

# Initialize FastMCP server with port configuration
mcp = FastMCP(
    "AIDP Retrieval API",
    host="0.0.0.0",
    port=MCP_PORT
)

# Milvus client (lazy initialization)
_milvus_client = None


def get_milvus_client():
    """Get or create Milvus client."""
    global _milvus_client
    if _milvus_client is None:
        _milvus_client = MilvusClient(uri=MILVUS_URI)
        logger.info(f"Connected to Milvus at {MILVUS_URI}")
    return _milvus_client


def get_embedding(text: str) -> list[float]:
    """Get embedding vector using NVIDIA NIM."""
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY not set")
    
    response = requests.post(
        NVIDIA_EMBED_URL,
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": NVIDIA_EMBED_MODEL,
            "input": [text],
            "input_type": "query",
            "encoding_format": "float",
            "truncate": "END"
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


@mcp.tool()
def search_vector_store(
    query: str,
    vector_store_id: str = "support_tickets",
    max_num_results: int = 10,
    filter_key: Optional[str] = None,
    filter_type: Optional[str] = None,
    filter_value: Optional[str] = None,
    score_threshold: Optional[float] = None
) -> str:
    """
    Search a vector store for relevant chunks based on a query.
    
    This tool implements the AIDP Retrieval API following the OpenAI specification.
    Use this to search the NVIDIA AI Data Platform for support tickets or other content.
    
    Args:
        query: A query string for search (required)
        vector_store_id: The ID of the vector store to search (default: support_tickets)
        max_num_results: Maximum number of results to return, 1-50 (default: 10)
        filter_key: Optional filter attribute key (e.g., "severity", "category")
        filter_type: Optional filter type: "eq", "ne", "contains"
        filter_value: Optional filter value to match
        score_threshold: Optional minimum score threshold for results
    
    Returns:
        JSON string with search results in OpenAI format
    """
    logger.info(f"search_vector_store called: query='{query}', store='{vector_store_id}'")
    
    try:
        client = get_milvus_client()
        
        # Check if collection exists
        if not client.has_collection(vector_store_id):
            return json.dumps({
                "error": {"code": 404, "message": f"Vector store '{vector_store_id}' not found"}
            })
        
        # Get query embedding
        query_embedding = get_embedding(query)
        
        # Validate max_num_results
        max_num_results = max(1, min(50, max_num_results))
        
        # Search Milvus
        search_results = client.search(
            collection_name=vector_store_id,
            data=[query_embedding],
            limit=max_num_results,
            output_fields=["pk", "title", "text", "category", "severity", "status"]
        )
        
        # Transform to OpenAI format
        data = []
        for hits in search_results:
            for hit in hits:
                entity = hit.get("entity", {})
                distance = hit.get("distance", 0)
                similarity_score = 1 / (1 + distance)
                
                # Apply score threshold
                if score_threshold and similarity_score < score_threshold:
                    continue
                
                # Apply filters
                if filter_key and filter_type and filter_value:
                    attr_value = entity.get(filter_key, "")
                    if filter_type == "eq" and attr_value != filter_value:
                        continue
                    elif filter_type == "ne" and attr_value == filter_value:
                        continue
                    elif filter_type == "contains" and filter_value not in str(attr_value):
                        continue
                
                result = {
                    "file_id": entity.get("pk", ""),
                    "filename": f"{entity.get('title', 'untitled')}.txt",
                    "score": round(similarity_score, 4),
                    "attributes": {
                        "category": entity.get("category", ""),
                        "severity": entity.get("severity", ""),
                        "status": entity.get("status", ""),
                        "title": entity.get("title", "")
                    },
                    "content": [
                        {
                            "type": "text",
                            "text": entity.get("text", "")
                        }
                    ]
                }
                data.append(result)
        
        # Build OpenAI-compatible response
        response = {
            "object": "vector_store.search_results.page",
            "search_query": query,
            "data": data,
            "has_more": False,
            "next_page": None
        }
        
        logger.info(f"Returning {len(data)} results")
        return json.dumps(response, indent=2)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return json.dumps({
            "error": {"code": 500, "message": str(e)}
        })


if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AIDP MCP Server (HTTP Transport)                          ║
║                    Following OpenAI Specification                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MCP Endpoint: http://localhost:{MCP_PORT}/mcp                                    ║
║  Tool: search_vector_store                                                   ║
║  Milvus: {MILVUS_URI:<55} ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Run the MCP server with HTTP transport
    mcp.run(transport="streamable-http")

