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
Load sample support ticket data into Milvus with NVIDIA NIM embeddings.

This script creates a collection and populates it with realistic tech support tickets.
"""
import asyncio
import os

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from pymilvus import Collection
from pymilvus import CollectionSchema
from pymilvus import DataType
from pymilvus import FieldSchema
from pymilvus import connections
from pymilvus import utility


async def generate_embeddings_with_nim(texts: list[str], api_key: str) -> list[list[float]]:
    """Generate embeddings for multiple texts using NVIDIA NIM API via langchain.

    Args:
        texts: List of text strings to embed
        api_key: NVIDIA API key

    Returns:
        List of embedding vectors (1024 dimensions each)
    """
    # Use langchain's NVIDIA embeddings which handles the API correctly
    embedder = NVIDIAEmbeddings(model="nvidia/nv-embedqa-e5-v5", truncate="END")

    # Set API key via environment (langchain reads from NVIDIA_API_KEY)
    os.environ["NVIDIA_API_KEY"] = api_key

    print(f"Generating embeddings for {len(texts)} tickets using NVIDIA NIM...")

    # Generate embeddings
    embeddings = await embedder.aembed_documents(texts)

    print(f"✓ Generated {len(embeddings)} embeddings (1024 dimensions each)")

    return embeddings


async def main():
    """Load support ticket data into Milvus with NIM embeddings."""
    # Check for API key
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        print("ERROR: NVIDIA_API_KEY environment variable not set!")
        print("Please set it: export NVIDIA_API_KEY='your-key'")
        return

    # Connect to Milvus
    connections.connect("default", host="localhost", port="19530")
    print("✓ Connected to Milvus")

    # Define schema for support tickets
    fields = [
        FieldSchema(name="record_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="ticket_id", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2000),
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="priority", dtype=DataType.VARCHAR, max_length=20),
        FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=20),
        # nvidia/nv-embedqa-e5-v5 returns 1024 dims
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
    ]

    schema = CollectionSchema(fields, "Tech support tickets for RAG demo")

    # Drop existing collection if exists
    if utility.has_collection("support_tickets"):
        utility.drop_collection("support_tickets")
        print("✓ Dropped existing support_tickets collection")

    # Create collection
    collection = Collection("support_tickets", schema)
    print("✓ Created support_tickets collection")

    # Sample support ticket data
    support_tickets = [
        {
            "ticket_id":
                "SUPPORT-2024-001",
            "category":
                "bug_report",
            "priority":
                "critical",
            "status":
                "open",
            "content": ("Customer reporting GPU driver crash on Windows 11 with RTX 4090. "
                        "Error code 0x00000116 VIDEO_TDR_ERROR. Occurs during CUDA workloads. "
                        "Driver version 546.12. System becomes unresponsive and requires hard reboot."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-002",
            "category":
                "feature_request",
            "priority":
                "medium",
            "status":
                "open",
            "content": ("Request for API rate limiting controls in NIM deployment. "
                        "Customer wants to set per-user quotas and throttling. "
                        "Currently using container-based deployment with 10 concurrent users. "
                        "Need monitoring dashboard for usage metrics."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-003",
            "category":
                "question",
            "priority":
                "low",
            "status":
                "resolved",
            "content": ("How to configure multi-GPU inference with TensorRT-LLM? "
                        "Customer has 8x A100 GPUs and wants to run Llama-3.1-70B with optimal performance. "
                        "Questions about tensor parallelism and pipeline parallelism settings."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-004",
            "category":
                "bug_report",
            "priority":
                "high",
            "status":
                "in_progress",
            "content": ("Memory leak detected in CUDA application after 6 hours of continuous operation. "
                        "Using CUDA 12.1 with custom kernels. Memory usage grows from 8GB to 24GB. "
                        "Suspected issue with stream synchronization and buffer cleanup."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-005",
            "category":
                "incident",
            "priority":
                "critical",
            "status":
                "resolved",
            "content": ("Production NIM endpoint returning 503 errors intermittently. "
                        "Peak traffic at 1000 req/sec. Load balancer shows healthy backends but requests timing out. "
                        "Issue resolved by scaling to 5 replicas and enabling connection pooling."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-006",
            "category":
                "question",
            "priority":
                "medium",
            "status":
                "resolved",
            "content": ("Customer asking about best practices for fine-tuning embedding models. "
                        "Want to improve retrieval accuracy for domain-specific technical documentation. "
                        "Dataset size 50k documents. Considering LoRA vs full fine-tuning approaches."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-007",
            "category":
                "bug_report",
            "priority":
                "high",
            "status":
                "open",
            "content": ("Triton Inference Server crashes when loading custom TensorRT engine. "
                        "Engine built for FP16 precision on A100. Error: incompatible plugin version. "
                        "Customer using Triton 24.03 container with TensorRT 10.0."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-008",
            "category":
                "feature_request",
            "priority":
                "low",
            "status":
                "open",
            "content": ("Request for Python SDK support for NeMo Guardrails. "
                        "Currently only REST API available. "
                        "Customer wants to integrate guardrails directly in their LangChain application. "
                        "Need async/await support and streaming responses."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-009",
            "category":
                "question",
            "priority":
                "medium",
            "status":
                "resolved",
            "content": ("How to optimize Milvus vector search performance for 100M embeddings? "
                        "Customer experiencing slow query times (>2s). Using IVF_FLAT index with nlist=16384. "
                        "Considering GPU acceleration with cuVS or switching to HNSW index."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-010",
            "category":
                "incident",
            "priority":
                "high",
            "status":
                "in_progress",
            "content": ("RAG application returning incorrect context chunks. "
                        "Reranker scores look correct but final results don't match query intent. "
                        "Using llama-3.2-nv-rerankqa-1b-v2. Customer suspects chunking strategy issue - "
                        "currently using 512 token chunks with 50 token overlap."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-011",
            "category":
                "bug_report",
            "priority":
                "medium",
            "status":
                "open",
            "content": ("NIM container fails to start with error: insufficient shared memory. "
                        "Running on Kubernetes with 16GB RAM limit. Container requesting 32GB /dev/shm. "
                        "Need guidance on proper resource allocation for llama-3.1-70b-instruct."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-012",
            "category":
                "feature_request",
            "priority":
                "medium",
            "status":
                "open",
            "content": ("Request for batch inference API in NIM. "
                        "Customer processing 10k documents daily for embedding generation. "
                        "Current sequential API calls taking 2 hours. "
                        "Need batch endpoint to reduce latency and improve throughput."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-013",
            "category":
                "question",
            "priority":
                "low",
            "status":
                "resolved",
            "content":
                ("What is the recommended approach for handling multilingual embeddings? "
                 "Customer has documents in English, Spanish, and Mandarin. "
                 "Asking whether to use separate collections per language or single multilingual embedding model."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-014",
            "category":
                "incident",
            "priority":
                "critical",
            "status":
                "resolved",
            "content": ("Complete system outage due to vector database corruption. "
                        "Milvus cluster lost quorum after network partition. 500GB of embeddings affected. "
                        "Resolved by restoring from backup and implementing proper disaster recovery procedures."),
        },
        {
            "ticket_id":
                "SUPPORT-2024-015",
            "category":
                "bug_report",
            "priority":
                "high",
            "status":
                "open",
            "content": ("Inconsistent results from reranking NIM between API calls. "
                        "Same query and document set producing different scores on repeated calls. "
                        "Using temperature=0 but still seeing variance. "
                        "Suspecting non-deterministic behavior in model inference."),
        },
    ]

    print(f"\n✓ Prepared {len(support_tickets)} support tickets")
    print("✓ Calling NVIDIA NIM API to generate embeddings...")

    # Generate embeddings using NVIDIA NIM
    contents = [ticket["content"] for ticket in support_tickets]
    embeddings = await generate_embeddings_with_nim(contents, api_key)

    print(f"✓ Generated {len(embeddings)} embeddings using NVIDIA NIM (nvidia/nv-embedqa-e5-v5)")

    # Prepare data for insertion
    ticket_ids = [ticket["ticket_id"] for ticket in support_tickets]
    categories = [ticket["category"] for ticket in support_tickets]
    priorities = [ticket["priority"] for ticket in support_tickets]
    statuses = [ticket["status"] for ticket in support_tickets]

    # Insert data
    data = [ticket_ids, contents, categories, priorities, statuses, embeddings]

    collection.insert(data)
    collection.flush()
    print(f"✓ Inserted {len(support_tickets)} tickets into Milvus")

    # Create index for vector search
    index_params = {"metric_type": "L2", "index_type": "IVF_FLAT", "params": {"nlist": 128}}
    collection.create_index(field_name="embedding", index_params=index_params)
    print("✓ Created vector index")

    # Load collection into memory
    collection.load()
    print("✓ Loaded collection into memory")

    print(f"\n{'='*60}")
    print(f"Successfully loaded {len(support_tickets)} support tickets into Milvus")
    print("Collection: support_tickets")
    print(f"{'='*60}")
    print("\nSample queries you can try:")
    print("- 'Find tickets about GPU driver crashes'")
    print("- 'Show me critical incidents'")
    print("- 'What bugs are related to CUDA?'")
    print("- 'Find feature requests for the API'")
    print("- 'Show me resolved Milvus performance issues'")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
