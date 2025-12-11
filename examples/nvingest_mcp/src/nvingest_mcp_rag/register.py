# SPDX-FileCopyrightText: Copyright (c) 2024-2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
NV-Ingest MCP RAG Example - Custom Function Registration

This module registers custom NAT functions that wrap NV-Ingest operations.
These functions can be exposed via MCP server for use by other workflows.

Aligned with the ingestion_text_only pattern from the main NV-Ingest API.
"""

import asyncio
import logging
import os
from typing import Optional

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


# =============================================================================
# FUNCTION 1: Document Ingest Function (Configurable extraction)
# =============================================================================

class DocumentIngestConfig(FunctionBaseConfig, name="nvingest_document_ingest"):
    """Configuration for the NV-Ingest document ingestion function."""

    nvingest_host: str = Field(
        default="localhost",
        description="Hostname of the NV-Ingest service"
    )
    nvingest_port: int = Field(
        default=7670,
        description="Port of the NV-Ingest service"
    )
    # Extraction options
    extract_text: bool = Field(
        default=True,
        description="Extract text content from documents"
    )
    extract_tables: bool = Field(
        default=False,
        description="Extract tables from documents"
    )
    extract_charts: bool = Field(
        default=False,
        description="Extract charts/graphics from documents"
    )
    extract_images: bool = Field(
        default=False,
        description="Extract images from documents"
    )
    text_depth: str = Field(
        default="page",
        description="Text extraction depth: 'page' or 'document'"
    )


@register_function(config_type=DocumentIngestConfig)
async def nvingest_document_ingest_function(config: DocumentIngestConfig, builder: Builder):
    """
    Ingest a document using NV-Ingest and return extracted text content.
    Text-only extraction - aligned with ingestion_text_only pattern.
    """
    from nv_ingest_client.client import Ingestor, NvIngestClient

    # Create client with proper configuration
    client = NvIngestClient(
        message_client_hostname=config.nvingest_host,
        message_client_port=config.nvingest_port,
    )

    async def _ingest_document(file_path: str) -> str:
        """
        Ingest a document and return extracted text content.

        Args:
            file_path: Path to the document file to ingest

        Returns:
            Extracted text content from the document as a string
        """
        logger.info(f"Ingesting document: {file_path}")

        # Validate file exists
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"

        try:
            # Create ingestor with client
            ingestor = Ingestor(client=client)

            # Configure pipeline with extraction options from config
            ingestor = ingestor.files(file_path)
            ingestor = ingestor.extract(
                extract_text=config.extract_text,
                extract_tables=config.extract_tables,
                extract_charts=config.extract_charts,
                extract_images=config.extract_images,
                text_depth=config.text_depth,
            )

            extraction_types = []
            if config.extract_text:
                extraction_types.append("text")
            if config.extract_tables:
                extraction_types.append("tables")
            if config.extract_charts:
                extraction_types.append("charts")
            if config.extract_images:
                extraction_types.append("images")
            logger.info(f"Extracting: {', '.join(extraction_types)}")

            # Run ingestion synchronously in thread
            results = await asyncio.to_thread(
                lambda: ingestor.ingest(show_progress=True)
            )

            # Extract content from results
            # NV-Ingest returns List[List[Dict]] - each inner list is chunks for one document
            extracted_content = []

            logger.info(f"Processing {len(results)} document results")

            for doc_idx, doc_chunks in enumerate(results):
                if isinstance(doc_chunks, list) and len(doc_chunks) > 0:
                    logger.info(f"Document {doc_idx}: {len(doc_chunks)} chunks")
                    for chunk in doc_chunks:
                        if isinstance(chunk, dict):
                            # Access per NV-Ingest MetadataSchema structure
                            metadata = chunk.get("metadata", {}) or {}
                            content = metadata.get("content", "")
                            content_type = metadata.get("content_metadata", {}).get("type", "text")
                            if content:
                                extracted_content.append(f"[{content_type}] {content}")

            if extracted_content:
                summary = f"Extracted {len(extracted_content)} chunks from {file_path}:\n\n"
                return summary + "\n\n---\n\n".join(extracted_content)
            else:
                return f"Document {file_path} was processed but no content was extracted."

        except Exception as e:
            logger.error(f"Error ingesting document: {e}", exc_info=True)
            return f"Error ingesting document: {str(e)}"

    yield FunctionInfo.from_fn(
        _ingest_document,
        description=(
            "Ingest a document using NV-Ingest to extract text content. "
            "Provide the file path to a PDF or other supported document type."
        )
    )


# =============================================================================
# FUNCTION 2: Document Ingest with VDB Upload Function
# =============================================================================

class DocumentIngestVDBConfig(FunctionBaseConfig, name="nvingest_document_ingest_vdb"):
    """Configuration for NV-Ingest document ingestion with VDB upload.
    Supports text, tables, charts, and images extraction.
    """

    nvingest_host: str = Field(
        default="localhost",
        description="Hostname of the NV-Ingest service"
    )
    nvingest_port: int = Field(
        default=7670,
        description="Port of the NV-Ingest service"
    )
    # Extraction options
    extract_text: bool = Field(
        default=True,
        description="Extract text content from documents"
    )
    extract_tables: bool = Field(
        default=False,
        description="Extract tables from documents"
    )
    extract_charts: bool = Field(
        default=False,
        description="Extract charts/graphics from documents"
    )
    extract_images: bool = Field(
        default=False,
        description="Extract images from documents"
    )
    text_depth: str = Field(
        default="page",
        description="Text extraction depth: 'page' or 'document'"
    )
    # VDB configuration
    milvus_uri: str = Field(
        default="http://localhost:19530",
        description="URI of the Milvus vector database"
    )
    collection_name: str = Field(
        default="nv_ingest_collection",
        description="Name of the Milvus collection to upload to"
    )
    embedding_url: str = Field(
        default="http://localhost:8012/v1",
        description="Endpoint URL for the embedding model"
    )
    embedding_model: str = Field(
        default="nvidia/llama-3.2-nv-embedqa-1b-v2",
        description="Name of the embedding model"
    )
    # MinIO configuration for multimodal storage
    minio_endpoint: str = Field(
        default="minio:9000",
        description="MinIO endpoint for storage"
    )
    minio_access_key: str = Field(
        default="minioadmin",
        description="MinIO access key"
    )
    minio_secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key"
    )


@register_function(config_type=DocumentIngestVDBConfig)
async def nvingest_document_ingest_vdb_function(config: DocumentIngestVDBConfig, builder: Builder):
    """
    Ingest a document using NV-Ingest, embed it, and upload to Milvus VDB.
    Text-only extraction - aligned with ingestion_text_only pattern.
    """
    from nv_ingest_client.client import Ingestor, NvIngestClient

    # Create client with proper configuration
    client = NvIngestClient(
        message_client_hostname=config.nvingest_host,
        message_client_port=config.nvingest_port,
    )

    async def _ingest_and_upload(file_path: str) -> str:
        """
        Ingest a document, embed content, and upload to vector database.

        Args:
            file_path: Path to the document file to ingest

        Returns:
            Status message indicating success or failure
        """
        # Build extraction types list for logging
        extraction_types = []
        if config.extract_text:
            extraction_types.append("text")
        if config.extract_tables:
            extraction_types.append("tables")
        if config.extract_charts:
            extraction_types.append("charts")
        if config.extract_images:
            extraction_types.append("images")

        # Log detailed configuration for visibility
        logger.info("=" * 60)
        logger.info("DOCUMENT INGEST WITH VDB UPLOAD")
        logger.info("=" * 60)
        logger.info(f"File path: {file_path}")
        logger.info(f"NV-Ingest: {config.nvingest_host}:{config.nvingest_port}")
        logger.info(f"Extraction: {', '.join(extraction_types)}")
        logger.info(f"Milvus URI: {config.milvus_uri}")
        logger.info(f"Collection name: {config.collection_name}")
        logger.info(f"Embedding URL: {config.embedding_url}")
        logger.info(f"Embedding model: {config.embedding_model}")
        logger.info(f"MinIO endpoint: {config.minio_endpoint}")
        logger.info("=" * 60)

        # Validate file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return f"Error: File not found: {file_path}"

        try:
            # Create ingestor with client
            logger.info("Creating NV-Ingest client and ingestor...")
            ingestor = Ingestor(client=client)

            # Build pipeline with configurable extraction
            logger.info("Configuring pipeline: files -> extract -> embed -> vdb_upload")
            ingestor = ingestor.files(file_path)

            ingestor = ingestor.extract(
                extract_text=config.extract_text,
                extract_tables=config.extract_tables,
                extract_charts=config.extract_charts,
                extract_images=config.extract_images,
                text_depth=config.text_depth,
            )
            logger.info(f"  - Extract: {', '.join(extraction_types)}, depth={config.text_depth}")

            # Embed with configured endpoint
            ingestor = ingestor.embed(
                endpoint_url=config.embedding_url,
                model_name=config.embedding_model
            )
            logger.info(f"  - Embed: {config.embedding_model}")

            # VDB upload with full configuration (following ingestion_text_only pattern)
            logger.info(f"  - VDB Upload: collection='{config.collection_name}' at {config.milvus_uri}")
            ingestor = ingestor.vdb_upload(
                milvus_uri=config.milvus_uri,
                collection_name=config.collection_name,
                recreate=False,
                stream=False,
                purge_results_after_upload=False,
                threshold=5000,
                minio_endpoint=config.minio_endpoint,
                access_key=config.minio_access_key,
                secret_key=config.minio_secret_key
            )

            # Execute pipeline in thread
            logger.info("Executing ingestion pipeline...")
            results, failures = await asyncio.to_thread(
                lambda: ingestor.ingest(return_failures=True, show_progress=True)
            )

            # Count uploaded items
            total_chunks = 0
            if results:
                for doc_chunks in results:
                    if isinstance(doc_chunks, list):
                        total_chunks += len(doc_chunks)

            logger.info("=" * 60)
            logger.info("INGESTION COMPLETE")
            logger.info(f"Total chunks uploaded: {total_chunks}")
            logger.info(f"Target collection: {config.collection_name}")
            logger.info(f"Milvus URI: {config.milvus_uri}")
            logger.info("=" * 60)

            # Check for failures
            if failures:
                logger.warning(f"Some failures during ingestion: {failures}")
                return (
                    f"Ingested {file_path} with {len(failures)} failures. "
                    f"Uploaded {total_chunks} chunks to collection '{config.collection_name}' "
                    f"at {config.milvus_uri}"
                )

            return (
                f"Successfully ingested {file_path} and uploaded {total_chunks} "
                f"chunks to Milvus collection '{config.collection_name}' at {config.milvus_uri}"
            )

        except Exception as e:
            logger.error(f"Error in ingest and upload: {e}", exc_info=True)
            return f"Error processing document: {str(e)}"

    yield FunctionInfo.from_fn(
        _ingest_and_upload,
        description=(
            "Ingest a document using NV-Ingest, generate embeddings, and upload to Milvus VDB. "
            "Use this to add documents to the knowledge base for later retrieval."
        )
    )


# =============================================================================
# FUNCTION 3: Milvus Query Function (for RAG retrieval)
# =============================================================================

class MilvusQueryConfig(FunctionBaseConfig, name="milvus_semantic_search"):
    """Configuration for Milvus semantic search function."""

    milvus_uri: str = Field(
        default="http://localhost:19530",
        description="URI of the Milvus vector database"
    )
    collection_name: str = Field(
        default="nv_ingest_collection",
        description="Name of the Milvus collection to search"
    )
    embedding_url: str = Field(
        default="http://localhost:8012/v1",
        description="Endpoint URL for the embedding model"
    )
    embedding_model: str = Field(
        default="nvidia/llama-3.2-nv-embedqa-1b-v2",
        description="Name of the embedding model"
    )
    top_k: int = Field(
        default=5,
        description="Number of top results to return"
    )


@register_function(config_type=MilvusQueryConfig)
async def milvus_semantic_search_function(config: MilvusQueryConfig, builder: Builder):
    """
    Perform semantic search on Milvus vector database using embeddings.
    """

    async def _semantic_search(query: str) -> str:
        """
        Search the Milvus collection for documents similar to the query.

        Args:
            query: The search query text

        Returns:
            Retrieved document content relevant to the query
        """
        logger.info("=" * 60)
        logger.info("SEMANTIC SEARCH")
        logger.info("=" * 60)
        logger.info(f"Query: {query}")
        logger.info(f"Milvus URI: {config.milvus_uri}")
        logger.info(f"Collection: {config.collection_name}")
        logger.info(f"Top K: {config.top_k}")
        logger.info(f"Embedding model: {config.embedding_model}")
        logger.info("=" * 60)

        try:
            from llama_index.embeddings.nvidia import NVIDIAEmbedding
            from pymilvus import MilvusClient

            # Create embedding for the query using same config as ingest
            logger.info("Creating query embedding...")
            embed_model = NVIDIAEmbedding(
                base_url=config.embedding_url,
                model=config.embedding_model
            )

            # Get query embedding
            query_embedding = await asyncio.to_thread(
                lambda: embed_model.get_query_embedding(query)
            )
            logger.info(f"Query embedding generated (dimension: {len(query_embedding)})")

            # Connect to Milvus and search
            logger.info(f"Connecting to Milvus at {config.milvus_uri}...")
            client = MilvusClient(uri=config.milvus_uri)

            # Check if collection exists
            collections = client.list_collections()
            logger.info(f"Available collections: {collections}")

            if config.collection_name not in collections:
                logger.warning(f"Collection '{config.collection_name}' does not exist!")
                return (
                    f"Collection '{config.collection_name}' does not exist in Milvus. "
                    f"Available collections: {collections}. "
                    "Please ingest documents first using document_ingest_vdb."
                )

            logger.info(f"Searching collection '{config.collection_name}'...")
            results = client.search(
                collection_name=config.collection_name,
                data=[query_embedding],
                limit=config.top_k,
                output_fields=["text"]
            )

            # Format results
            retrieved_texts = []
            for hits in results:
                for hit in hits:
                    text = hit.get("entity", {}).get("text", "")
                    if text:
                        retrieved_texts.append(text)

            logger.info(f"Found {len(retrieved_texts)} results")

            if retrieved_texts:
                return f"Found {len(retrieved_texts)} relevant documents from collection '{config.collection_name}':\n\n" + "\n\n---\n\n".join(retrieved_texts)
            else:
                return (
                    f"No relevant documents found in collection '{config.collection_name}'. "
                    "The collection may be empty - try ingesting documents first using document_ingest_vdb."
                )

        except Exception as e:
            logger.error(f"Error in semantic search: {e}", exc_info=True)
            return f"Error performing search: {str(e)}"

    yield FunctionInfo.from_fn(
        _semantic_search,
        description=(
            "Search the knowledge base for documents relevant to the query. "
            "Returns the most relevant document content from Milvus VDB."
        )
    )

