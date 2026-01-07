# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3
"""
AIDP Retrieval API - REST Server Implementation

This REST server implements the NVIDIA AI Data Platform (AIDP) Retrieval API
following the OpenAI API specification exactly.

Endpoint: POST /v1/vector_stores/{vector_store_id}/search

Request Body:
{
    "query": "string",              # Required
    "filters": {...},               # Optional
    "max_num_results": 10,          # Optional (1-50)
    "ranking_options": {...},       # Optional
    "rewrite_query": false          # Optional
}

Response Body:
{
    "object": "vector_store.search_results.page",
    "search_query": "...",
    "data": [...],
    "has_more": false,
    "next_page": null
}

Usage:
    python rest_api.py
    
    # Then call:
    curl -X POST http://localhost:8080/v1/vector_stores/support_tickets/search \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $NVIDIA_API_KEY" \
        -d '{"query": "GPU memory issues"}'
"""

import os
import json
import logging
from typing import Optional, List, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from pymilvus import MilvusClient
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aidp-rest-api")

# Configuration
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
API_PORT = int(os.getenv("AIDP_API_PORT", "8080"))


# ============================================================================
# Pydantic Models - Following OpenAI API Specification
# ============================================================================

class FilterSpec(BaseModel):
    """Filter specification for attribute-based filtering."""
    key: str = Field(..., description="The attribute key to filter on")
    type: str = Field("eq", description="Filter type: eq, ne, contains")
    value: str = Field(..., description="The value to filter by")


class RankingOptions(BaseModel):
    """Ranking options for search results."""
    ranker: str = Field("auto", description="Ranker to use")
    score_threshold: Optional[float] = Field(None, description="Minimum score threshold")


class SearchRequest(BaseModel):
    """
    Search request body following OpenAI API specification.
    https://platform.openai.com/docs/api-reference/vector_stores/search
    """
    query: str = Field(..., description="A query string for search")
    filters: Optional[FilterSpec] = Field(None, description="Filters to apply based on file attributes")
    max_num_results: int = Field(10, ge=1, le=50, description="Maximum number of results (1-50)")
    ranking_options: Optional[RankingOptions] = Field(None, description="Ranking options for search")
    rewrite_query: bool = Field(False, description="Whether to rewrite the query for vector search")


class ContentItem(BaseModel):
    """Content item within a search result."""
    type: str = "text"
    text: str
    location: Optional[dict] = None


class SearchResultItem(BaseModel):
    """Individual search result following OpenAI format."""
    file_id: str
    filename: str
    score: float
    attributes: dict
    content: List[ContentItem]


class SearchResponse(BaseModel):
    """
    Search response body following OpenAI API specification.
    https://platform.openai.com/docs/api-reference/vector_stores/search
    """
    object: str = "vector_store.search_results.page"
    search_query: str
    data: List[SearchResultItem]
    has_more: bool = False
    next_page: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: dict


# ============================================================================
# Retrieval Service
# ============================================================================

class AIDPRetrievalService:
    """AIDP Retrieval API service implementation."""
    
    def __init__(self):
        self.milvus_client = None
        self.api_key = NVIDIA_API_KEY
    
    def connect(self):
        """Connect to Milvus."""
        if self.milvus_client is None:
            self.milvus_client = MilvusClient(uri=MILVUS_URI)
            logger.info(f"Connected to Milvus at {MILVUS_URI}")
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding vector using NVIDIA NIM."""
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY not set. Get one from https://build.nvidia.com")
        
        response = requests.post(
            NVIDIA_EMBED_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
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
    
    def search(
        self,
        vector_store_id: str,
        request: SearchRequest
    ) -> SearchResponse:
        """
        Search vector store following OpenAI API specification.
        """
        self.connect()
        
        logger.info(f"Searching '{vector_store_id}' with query: {request.query}")
        
        # Check if collection exists
        if not self.milvus_client.has_collection(vector_store_id):
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{vector_store_id}' not found"
            )
        
        # Get query embedding
        query_embedding = self._get_embedding(request.query)
        
        # Search Milvus
        search_results = self.milvus_client.search(
            collection_name=vector_store_id,
            data=[query_embedding],
            limit=request.max_num_results,
            output_fields=["pk", "title", "text", "category", "severity", "status"]
        )
        
        # Transform to OpenAI format
        data = []
        for hits in search_results:
            for hit in hits:
                entity = hit.get("entity", {})
                
                # Calculate similarity score from L2 distance
                distance = hit.get("distance", 0)
                similarity_score = 1 / (1 + distance)
                
                # Apply score threshold if specified
                if request.ranking_options and request.ranking_options.score_threshold:
                    if similarity_score < request.ranking_options.score_threshold:
                        continue
                
                # Apply filters if specified
                if request.filters:
                    attr_value = None
                    if request.filters.key == "category":
                        attr_value = entity.get("category", "")
                    elif request.filters.key == "severity":
                        attr_value = entity.get("severity", "")
                    elif request.filters.key == "status":
                        attr_value = entity.get("status", "")
                    
                    if attr_value:
                        if request.filters.type == "eq" and attr_value != request.filters.value:
                            continue
                        elif request.filters.type == "ne" and attr_value == request.filters.value:
                            continue
                        elif request.filters.type == "contains" and request.filters.value not in attr_value:
                            continue
                
                result = SearchResultItem(
                    file_id=entity.get("pk", ""),
                    filename=f"{entity.get('title', 'untitled')}.txt",
                    score=round(similarity_score, 4),
                    attributes={
                        "category": entity.get("category", ""),
                        "severity": entity.get("severity", ""),
                        "status": entity.get("status", ""),
                        "title": entity.get("title", "")
                    },
                    content=[
                        ContentItem(
                            type="text",
                            text=entity.get("text", "")
                        )
                    ]
                )
                data.append(result)
        
        logger.info(f"Found {len(data)} results")
        
        return SearchResponse(
            object="vector_store.search_results.page",
            search_query=request.query,
            data=data,
            has_more=False,
            next_page=None
        )


# Initialize service
retrieval_service = AIDPRetrievalService()


# ============================================================================
# FastAPI Application
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting AIDP Retrieval API Server...")
    retrieval_service.connect()
    yield
    logger.info("Shutting down AIDP Retrieval API Server...")


app = FastAPI(
    title="AIDP Retrieval API",
    description="NVIDIA AI Data Platform Retrieval API following OpenAI specification",
    version="0.2",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Authentication
# ============================================================================

async def verify_api_key(authorization: Optional[str] = Header(None)):
    """
    Verify Bearer token authentication.
    API keys provided as Bearer tokens are the recommended authentication method.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authentication. Please provide Authorization header with Bearer token."
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authentication. Use 'Bearer <token>' format."
        )
    
    # For demo purposes, we accept any non-empty token
    # In production, validate against your auth system
    token = authorization.replace("Bearer ", "")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Incorrect API Key provided."
        )
    
    return token


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API root - health check."""
    return {
        "name": "AIDP Retrieval API",
        "version": "0.2",
        "status": "healthy",
        "spec": "OpenAI Vector Store Search API"
    }


@app.get("/v1/vector_stores")
async def list_vector_stores(api_key: str = Depends(verify_api_key)):
    """List available vector stores."""
    retrieval_service.connect()
    collections = retrieval_service.milvus_client.list_collections()
    return {
        "object": "list",
        "data": [
            {"id": name, "object": "vector_store"}
            for name in collections
        ]
    }


@app.post(
    "/v1/vector_stores/{vector_store_id}/search",
    response_model=SearchResponse,
    responses={
        200: {"description": "Search results"},
        401: {"description": "Invalid Authentication"},
        404: {"description": "Vector store not found"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
        503: {"description": "System overloaded"}
    }
)
async def search_vector_store(
    vector_store_id: str = Path(..., description="The ID of the vector store (collection) to search"),
    request: SearchRequest = ...,
    api_key: str = Depends(verify_api_key)
):
    """
    Search a vector store for relevant chunks based on a query and file attributes filter.
    
    This endpoint implements the OpenAI Vector Store Search API specification
    as defined in the AIDP Storage API Proposal.
    
    URL: POST /v1/vector_stores/{vector_store_id}/search
    
    See: https://platform.openai.com/docs/api-reference/vector_stores/search
    """
    try:
        return retrieval_service.search(vector_store_id, request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal system error: {str(e)}"
        )


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AIDP Retrieval API Server                                  ║
║                    Following OpenAI Specification                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Endpoint: POST /v1/vector_stores/{{vector_store_id}}/search                   ║
║  Port: {API_PORT}                                                                  ║
║  Milvus: {MILVUS_URI:<55} ║
╚══════════════════════════════════════════════════════════════════════════════╝

Example usage:
    curl -X POST http://localhost:{API_PORT}/v1/vector_stores/support_tickets/search \\
        -H "Content-Type: application/json" \\
        -H "Authorization: Bearer your-api-key" \\
        -d '{{"query": "GPU memory issues", "max_num_results": 5}}'
""")
    
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

