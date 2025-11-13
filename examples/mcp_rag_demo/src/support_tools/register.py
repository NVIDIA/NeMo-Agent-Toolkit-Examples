# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Support Ticket Tools - NAT Functions for MCP Server Demo
Demonstrates how to create custom tools and serve them via MCP
"""

from pydantic import BaseModel
from pydantic import Field
from pymilvus import MilvusClient

from nat.builder.builder import Builder
from nat.builder.builder import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig


class SearchSupportTicketsConfig(FunctionBaseConfig, name="search_support_tickets"):
    """Search support tickets using semantic similarity with NVIDIA NIM embeddings."""

    milvus_uri: str = Field(default="http://localhost:19530", description="Milvus connection URI")
    collection_name: str = Field(default="support_tickets", description="Milvus collection name")
    embedder_name: str = Field(description="Name of the embedder to use for query embedding")
    top_k: int = Field(default=5, description="Number of results to return")


class QueryByCategoryConfig(FunctionBaseConfig, name="query_by_category"):
    """Query support tickets by category filter."""

    milvus_uri: str = Field(default="http://localhost:19530", description="Milvus connection URI")
    collection_name: str = Field(default="support_tickets", description="Milvus collection name")
    top_k: int = Field(default=10, description="Number of results to return")


class QueryByPriorityConfig(FunctionBaseConfig, name="query_by_priority"):
    """Query support tickets by priority filter."""

    milvus_uri: str = Field(default="http://localhost:19530", description="Milvus connection URI")
    collection_name: str = Field(default="support_tickets", description="Milvus collection name")
    top_k: int = Field(default=10, description="Number of results to return")


class RerankResultsConfig(FunctionBaseConfig, name="rerank_support_tickets"):
    """Rerank search results using NVIDIA reranking NIM for improved accuracy."""

    reranker_name: str = Field(description="Name of the reranker model to use")
    top_k: int = Field(default=5, description="Number of top results to return after reranking")


@register_function(config_type=SearchSupportTicketsConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def search_support_tickets_tool(config: SearchSupportTicketsConfig, builder: Builder):
    """Search support tickets using semantic similarity with NVIDIA NIM embeddings."""

    # Get the embedder from builder (NAT handles the NIM API calls)
    embedder = await builder.get_embedder(config.embedder_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    class SearchInput(BaseModel):
        query: str = Field(description="Search query for support tickets")
        limit: int = Field(default=config.top_k, description="Maximum number of results")

    async def _search(query: str, limit: int = config.top_k) -> str:
        """Search support tickets using semantic similarity."""
        try:
            milvus_client = MilvusClient(uri=config.milvus_uri)
            query_embedding = await embedder.aembed_query(query)

            results = milvus_client.search(collection_name=config.collection_name,
                                           data=[query_embedding],
                                           anns_field="embedding",
                                           limit=limit,
                                           output_fields=["ticket_id", "content", "category", "priority", "status"])

            if not results or not results[0]:
                return f"No support tickets found matching '{query}'"

            output = f"Search results for '{query}':\n\n"
            for idx, hit in enumerate(results[0], 1):
                entity = hit['entity']
                score = hit.get('distance', 0)
                output += f"{idx}. Ticket: {entity['ticket_id']}\n"
                output += f"   Category: {entity['category']}\n"
                output += f"   Priority: {entity['priority']}\n"
                output += f"   Status: {entity['status']}\n"
                output += f"   Similarity: {1 - score:.3f}\n"
                output += f"   Content: {entity['content'][:150]}...\n\n"

            return output

        except Exception as e:
            return f"Error searching tickets: {str(e)}"

    yield FunctionInfo.from_fn(
        _search,
        input_schema=SearchInput,
        description="Search support tickets using semantic similarity with NVIDIA NIM embeddings")


@register_function(config_type=QueryByCategoryConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def query_by_category_tool(config: QueryByCategoryConfig, builder: Builder):
    """Query support tickets by category filter."""

    class CategoryInput(BaseModel):
        category: str = Field(description="Category: bug_report, feature_request, question, or incident")
        limit: int = Field(default=config.top_k, description="Maximum number of results")

    async def _query_category(category: str, limit: int = config.top_k) -> str:
        """Query support tickets by category."""
        try:
            milvus_client = MilvusClient(uri=config.milvus_uri)
            results = milvus_client.query(collection_name=config.collection_name,
                                          filter=f'category == "{category}"',
                                          output_fields=["ticket_id", "content", "priority", "status"],
                                          limit=limit)

            if not results:
                return f"No tickets found in category '{category}'"

            output = f"Tickets in category '{category}' ({len(results)} found):\n\n"
            for result in results:
                output += f"Ticket: {result['ticket_id']}\n"
                output += f"Priority: {result['priority']}\n"
                output += f"Status: {result['status']}\n"
                output += f"Content: {result['content'][:150]}...\n\n"

            return output

        except Exception as e:
            return f"Error querying by category: {str(e)}"

    yield FunctionInfo.from_fn(_query_category,
                               input_schema=CategoryInput,
                               description="Query support tickets filtered by category")


@register_function(config_type=QueryByPriorityConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def query_by_priority_tool(config: QueryByPriorityConfig, builder: Builder):
    """Query support tickets by priority filter."""

    class PriorityInput(BaseModel):
        priority: str = Field(description="Priority level: critical, high, medium, or low")
        limit: int = Field(default=config.top_k, description="Maximum number of results")

    async def _query_priority(priority: str, limit: int = config.top_k) -> str:
        """Query support tickets by priority level."""
        try:
            milvus_client = MilvusClient(uri=config.milvus_uri)
            results = milvus_client.query(collection_name=config.collection_name,
                                          filter=f'priority == "{priority}"',
                                          output_fields=["ticket_id", "content", "category", "status"],
                                          limit=limit)

            if not results:
                return f"No tickets found with priority '{priority}'"

            output = f"Tickets with priority '{priority}' ({len(results)} found):\n\n"
            for result in results:
                output += f"Ticket: {result['ticket_id']}\n"
                output += f"Category: {result['category']}\n"
                output += f"Status: {result['status']}\n"
                output += f"Content: {result['content'][:150]}...\n\n"

            return output

        except Exception as e:
            return f"Error querying by priority: {str(e)}"

    yield FunctionInfo.from_fn(_query_priority,
                               input_schema=PriorityInput,
                               description="Query support tickets filtered by priority level")


@register_function(config_type=RerankResultsConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def rerank_support_tickets_tool(config: RerankResultsConfig, builder: Builder):
    """Rerank search results using NVIDIA reranking NIM."""

    # Get reranker from builder
    from langchain_nvidia_ai_endpoints import NVIDIARerank

    reranker = NVIDIARerank(model=config.reranker_name, top_n=config.top_k)

    class RerankInput(BaseModel):
        query: str = Field(description="The original search query")
        documents: list[str] = Field(description="List of document contents to rerank")

    async def _rerank(query: str, documents: list[str]) -> str:
        """Rerank documents by relevance to query using NVIDIA NIM."""
        try:
            if not documents:
                return "No documents provided for reranking"

            # Create document objects for reranking
            from langchain_core.documents import Document
            docs = [Document(page_content=doc) for doc in documents]

            # Rerank using NVIDIA NIM
            reranked = await reranker.acompress_documents(documents=docs, query=query)

            # Format results
            output = f"Reranked results for query '{query}' (top {len(reranked)}):\n\n"
            for idx, doc in enumerate(reranked, 1):
                relevance_score = getattr(doc, 'metadata', {}).get('relevance_score', 'N/A')
                output += f"{idx}. Relevance: {relevance_score}\n"
                output += f"   Content: {doc.page_content[:200]}...\n\n"

            return output

        except Exception as e:
            return f"Error reranking results: {str(e)}"

    yield FunctionInfo.from_fn(
        _rerank,
        input_schema=RerankInput,
        description="Rerank search results using NVIDIA reranking NIM to improve relevance and accuracy")
