# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3
"""
================================================================================
AIDP Retrieval API Example
================================================================================

This example demonstrates the NVIDIA AI Data Platform (AIDP) Retrieval API
and its alignment with OpenAI-compliant search endpoints.

AIDP API Specification:
-----------------------
The AIDP Retrieval API follows the OpenAI Vector Store Search API specification:
https://platform.openai.com/docs/api-reference/vector_stores/search

Endpoint:
    POST /v1/vector_stores/{vector_store_id}/search

Request Body:
    {
        "query": "search query string",
        "filters": {"key": "...", "type": "eq", "value": "..."},
        "max_num_results": 10,
        "ranking_options": {"ranker": "auto", "score_threshold": 0.5},
        "rewrite_query": false
    }

Response Body (OpenAI Format):
    {
        "object": "vector_store.search_results.page",
        "search_query": "...",
        "data": [
            {
                "file_id": "...",
                "filename": "...",
                "score": 0.95,
                "attributes": {...},
                "content": [{"type": "text", "text": "..."}]
            }
        ],
        "has_more": false,
        "next_page": null
    }

Usage:
    # Start the AIDP REST API server first:
    python rest_api.py &
    
    # Then run this example:
    python examples.py
"""

import os
import json
import requests
from typing import Optional

# Configuration
AIDP_API_BASE = os.getenv("AIDP_API_BASE", "http://localhost:8080")
API_KEY = os.getenv("NVIDIA_API_KEY", "demo-api-key")


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subheader(title: str):
    """Print a formatted subheader."""
    print(f"\n{'─' * 40}")
    print(f"  {title}")
    print(f"{'─' * 40}")


def search_vector_store(
    vector_store_id: str,
    query: str,
    max_num_results: int = 10,
    filters: Optional[dict] = None,
    ranking_options: Optional[dict] = None
) -> dict:
    """
    Call the AIDP Retrieval API following OpenAI specification.
    
    This function demonstrates the exact API call format as specified
    in the AIDP Storage API Proposal.
    
    Endpoint: POST /v1/vector_stores/{vector_store_id}/search
    
    Args:
        vector_store_id: The ID of the vector store (collection) to search
        query: A query string for search (required)
        max_num_results: Maximum results to return, 1-50 (default: 10)
        filters: Optional filters based on file attributes
        ranking_options: Optional ranking configuration
    
    Returns:
        OpenAI-compatible search response
    """
    url = f"{AIDP_API_BASE}/v1/vector_stores/{vector_store_id}/search"
    
    # Build request body (OpenAI format)
    request_body = {
        "query": query,
        "max_num_results": max_num_results
    }
    
    if filters:
        request_body["filters"] = filters
    
    if ranking_options:
        request_body["ranking_options"] = ranking_options
    
    # Make the API call with Bearer token authentication
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"  # AIDP uses Bearer token auth
        },
        json=request_body,
        timeout=30
    )
    
    response.raise_for_status()
    return response.json()


def example_1_basic_search():
    """Example 1: Basic semantic search."""
    print_header("Example 1: Basic Semantic Search")
    
    print("""
This example demonstrates a basic semantic search following the OpenAI API spec.

API Call:
    POST /v1/vector_stores/support_tickets/search
    
    Request Body:
    {
        "query": "GPU memory issues during training",
        "max_num_results": 3
    }
""")
    
    result = search_vector_store(
        vector_store_id="support_tickets",
        query="GPU memory issues during training",
        max_num_results=3
    )
    
    print("Response (OpenAI Format):")
    print(f"  object: {result.get('object')}")
    print(f"  search_query: {result.get('search_query')}")
    print(f"  has_more: {result.get('has_more')}")
    print(f"\n  Results ({len(result.get('data', []))} found):")
    
    for i, item in enumerate(result.get("data", []), 1):
        print(f"\n  {i}. {item['attributes']['title']}")
        print(f"     file_id: {item['file_id']}")
        print(f"     score: {item['score']}")
        print(f"     category: {item['attributes']['category']}")
        print(f"     severity: {item['attributes']['severity']}")


def example_2_filtered_search():
    """Example 2: Search with attribute filters."""
    print_header("Example 2: Search with Attribute Filters")
    
    print("""
This example demonstrates filtering by file attributes (severity=critical).

API Call:
    POST /v1/vector_stores/support_tickets/search
    
    Request Body:
    {
        "query": "GPU issues",
        "max_num_results": 5,
        "filters": {
            "key": "severity",
            "type": "eq",
            "value": "critical"
        }
    }
""")
    
    result = search_vector_store(
        vector_store_id="support_tickets",
        query="GPU issues",
        max_num_results=5,
        filters={
            "key": "severity",
            "type": "eq",
            "value": "critical"
        }
    )
    
    print("Response:")
    print(f"  Found {len(result.get('data', []))} critical issues:")
    
    for i, item in enumerate(result.get("data", []), 1):
        print(f"\n  {i}. {item['attributes']['title']}")
        print(f"     severity: {item['attributes']['severity']} ✓")
        print(f"     score: {item['score']}")


def example_3_category_filter():
    """Example 3: Filter by category."""
    print_header("Example 3: Filter by Category")
    
    print("""
This example filters results by category.

API Call:
    POST /v1/vector_stores/support_tickets/search
    
    Request Body:
    {
        "query": "performance problems",
        "filters": {
            "key": "category",
            "type": "eq",
            "value": "Driver Issues"
        }
    }
""")
    
    result = search_vector_store(
        vector_store_id="support_tickets",
        query="performance problems",
        max_num_results=5,
        filters={
            "key": "category",
            "type": "eq",
            "value": "Driver Issues"
        }
    )
    
    print("Response:")
    print(f"  Found {len(result.get('data', []))} Driver Issues:")
    
    for i, item in enumerate(result.get("data", []), 1):
        print(f"\n  {i}. {item['attributes']['title']}")
        print(f"     category: {item['attributes']['category']} ✓")


def example_4_full_response_format():
    """Example 4: Show complete OpenAI response format."""
    print_header("Example 4: Complete OpenAI Response Format")
    
    print("""
This example shows the complete OpenAI-compatible response format
as specified in the AIDP Storage API Proposal.
""")
    
    result = search_vector_store(
        vector_store_id="support_tickets",
        query="container Kubernetes GPU",
        max_num_results=2
    )
    
    print("Full JSON Response:")
    print(json.dumps(result, indent=2))


def example_5_openai_alignment():
    """Example 5: OpenAI API alignment comparison."""
    print_header("Example 5: OpenAI API Alignment")
    
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    AIDP API vs OpenAI API Alignment                           ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  OpenAI Specification                    AIDP Implementation                  ║
║  ────────────────────────────────────    ────────────────────────────────     ║
║                                                                               ║
║  Endpoint:                                                                    ║
║  POST /v1/vector_stores/{id}/search      ✓ Identical                         ║
║                                                                               ║
║  Request Parameters:                                                          ║
║  • query (required)                      ✓ Implemented                        ║
║  • max_num_results (1-50)                ✓ Implemented                        ║
║  • filters (key/type/value)              ✓ Implemented                        ║
║  • ranking_options                       ✓ Implemented                        ║
║  • rewrite_query                         ✓ Implemented (placeholder)          ║
║                                                                               ║
║  Response Format:                                                             ║
║  • object: "vector_store.search..."      ✓ Identical                         ║
║  • search_query                          ✓ Identical                         ║
║  • data[].file_id                        ✓ Identical                         ║
║  • data[].filename                       ✓ Identical                         ║
║  • data[].score                          ✓ Identical                         ║
║  • data[].attributes                     ✓ Identical                         ║
║  • data[].content[]                      ✓ Identical                         ║
║  • has_more                              ✓ Identical                         ║
║  • next_page                             ✓ Identical                         ║
║                                                                               ║
║  Authentication:                                                              ║
║  Bearer token                            ✓ Implemented                        ║
║                                                                               ║
║  HTTP Status Codes:                                                           ║
║  200, 401, 404, 429, 500, 503           ✓ All implemented                    ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
""")


def main():
    """Run all examples."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║              NVIDIA AI Data Platform (AIDP) Retrieval API                     ║
║                                                                               ║
║                     OpenAI-Compliant Search Endpoints                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This demonstration shows how the AIDP Retrieval API aligns with the OpenAI
Vector Store Search API specification, enabling seamless integration with
AI agents and enterprise applications.

Reference: AIDP Storage API Proposal v0.2
OpenAI Spec: https://platform.openai.com/docs/api-reference/vector_stores/search
""")
    
    try:
        # Check if API is available
        response = requests.get(f"{AIDP_API_BASE}/", timeout=5)
        if response.status_code != 200:
            raise Exception("API not available")
        
        print(f"✓ AIDP API Server running at {AIDP_API_BASE}")
        
    except Exception as e:
        print(f"""
✗ AIDP API Server not running at {AIDP_API_BASE}

Please start the server first:
    python rest_api.py &

Then run this example again.
""")
        return
    
    # Run examples
    try:
        example_1_basic_search()
        example_2_filtered_search()
        example_3_category_filter()
        example_4_full_response_format()
        example_5_openai_alignment()
        
        print_header("Summary")
        print("""
The AIDP Retrieval API provides:

1. ✓ OpenAI-Compatible Endpoint
   POST /v1/vector_stores/{vector_store_id}/search

2. ✓ Standard Request Format
   query, filters, max_num_results, ranking_options

3. ✓ OpenAI Response Schema
   object, search_query, data[], has_more, next_page

4. ✓ Bearer Token Authentication
   As recommended in the AIDP Storage API Proposal

5. ✓ MCP Integration
   Exposes search_vector_store tool for AI agent discovery

This alignment ensures that any AI application built for OpenAI's
Vector Store API can seamlessly integrate with NVIDIA AIDP storage.
""")
        
    except requests.exceptions.RequestException as e:
        print(f"\n✗ API Error: {e}")
        print("Please ensure the AIDP API server is running.")


if __name__ == "__main__":
    main()

