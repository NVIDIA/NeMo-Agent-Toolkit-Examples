# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3
"""
Seed Milvus with synthetic support tickets using NVIDIA NIMs.

This script:
1. Generates synthetic support tickets using NVIDIA Nemotron LLM
2. Embeds the tickets using NVIDIA NIM embeddings
3. Stores them in a Milvus collection for RAG retrieval
"""

import os
import json
import requests
from typing import List, Dict
from pymilvus import MilvusClient, DataType

# Configuration
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
COLLECTION_NAME = "support_tickets"
EMBEDDING_MODEL = "nvidia/nv-embedqa-e5-v5"
LLM_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"
EMBEDDING_DIM = 1024  # Dimension for nv-embedqa-e5-v5

# NVIDIA API endpoints
NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def get_nvidia_headers():
    """Get headers for NVIDIA API requests."""
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY environment variable is not set. "
                        "Get one from https://build.nvidia.com")
    return {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using NVIDIA NIM."""
    headers = get_nvidia_headers()
    
    payload = {
        "input": texts,
        "model": EMBEDDING_MODEL,
        "input_type": "passage",
        "encoding_format": "float",
        "truncate": "END"
    }
    
    response = requests.post(NVIDIA_EMBED_URL, headers=headers, json=payload)
    response.raise_for_status()
    
    result = response.json()
    embeddings = [item["embedding"] for item in result["data"]]
    return embeddings


def generate_synthetic_tickets(num_tickets: int = 50) -> List[Dict]:
    """Generate synthetic support tickets using NVIDIA Nemotron LLM."""
    headers = get_nvidia_headers()
    
    categories = [
        "GPU Hardware", "CUDA Software", "Driver Issues", "Memory Problems",
        "Performance Optimization", "Container/Docker", "Multi-GPU Setup",
        "TensorRT", "cuDNN", "NVIDIA NIM", "DeepStream", "Triton Inference"
    ]
    
    prompt = f"""Generate {num_tickets} diverse technical support tickets for an NVIDIA data center platform.
Each ticket should be a realistic IT support issue that a data center administrator might encounter.

For each ticket, provide:
- title: A concise summary of the issue (max 100 chars)
- content: Detailed description including symptoms, error messages, and context (200-500 chars)
- category: One of these categories: {', '.join(categories)}
- severity: critical, high, medium, or low
- status: open, in_progress, or resolved

Return as a JSON array with exactly {num_tickets} tickets. Only output valid JSON, no markdown.

Example format:
[
  {{
    "title": "GPU driver crash on reboot after kernel update",
    "content": "After updating to kernel 5.15, the NVIDIA driver fails to load on system reboot. dmesg shows 'NVRM: GPU at 0000:01:00.0 has fallen off the bus'. System: DGX A100, Driver: 535.129.03. Issue occurs consistently after warm reboot but not after cold boot.",
    "category": "Driver Issues",
    "severity": "critical",
    "status": "open"
  }}
]"""

    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 8000
    }
    
    print(f"Generating {num_tickets} synthetic support tickets using {LLM_MODEL}...")
    response = requests.post(NVIDIA_LLM_URL, headers=headers, json=payload)
    response.raise_for_status()
    
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    
    # Parse the JSON response
    try:
        # Clean up potential markdown formatting
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        tickets = json.loads(content.strip())
        print(f"Successfully generated {len(tickets)} tickets")
        return tickets
    except json.JSONDecodeError as e:
        print(f"Failed to parse LLM response as JSON: {e}")
        print(f"Response content: {content[:500]}...")
        # Return fallback tickets
        return get_fallback_tickets()


def get_fallback_tickets() -> List[Dict]:
    """Return fallback tickets if LLM generation fails."""
    return [
        {
            "title": "GPU driver crash on reboot after kernel update",
            "content": "After updating to kernel 5.15, the NVIDIA driver fails to load on system reboot. dmesg shows 'NVRM: GPU at 0000:01:00.0 has fallen off the bus'. System: DGX A100, Driver: 535.129.03. Issue occurs consistently after warm reboot but not after cold boot.",
            "category": "Driver Issues",
            "severity": "critical",
            "status": "open"
        },
        {
            "title": "CUDA out of memory error with large batch sizes",
            "content": "Training transformer model with batch size 64 causes 'CUDA out of memory' error on A100 80GB. nvidia-smi shows only 45GB used before crash. Suspecting memory fragmentation. Using PyTorch 2.1, CUDA 12.1. Issue started after upgrading from PyTorch 1.13.",
            "category": "Memory Problems",
            "severity": "high",
            "status": "in_progress"
        },
        {
            "title": "Multi-GPU training hangs at NCCL initialization",
            "content": "4-GPU training job freezes during NCCL backend initialization. No error messages, process just hangs. Using torchrun with NCCL 2.18.1. Single GPU training works fine. Network fabric is InfiniBand. Verified all GPUs visible via nvidia-smi.",
            "category": "Multi-GPU Setup",
            "severity": "high",
            "status": "open"
        },
        {
            "title": "TensorRT engine build fails on INT8 quantization",
            "content": "Building TensorRT engine with INT8 calibration fails with 'Calibration cache is not valid'. Using TensorRT 8.6.1, calibration dataset has 1000 samples. FP16 engine builds successfully. Model is ResNet-50 exported from PyTorch.",
            "category": "TensorRT",
            "severity": "medium",
            "status": "open"
        },
        {
            "title": "Container GPU isolation not working in Kubernetes",
            "content": "NVIDIA device plugin not properly isolating GPUs between pods. Pod A can see GPUs allocated to Pod B. Using k8s 1.28, nvidia-device-plugin 0.14.1. NVIDIA_VISIBLE_DEVICES environment variable is set correctly but nvidia-smi shows all 8 GPUs.",
            "category": "Container/Docker",
            "severity": "high",
            "status": "in_progress"
        },
        {
            "title": "Triton Inference Server high latency spikes",
            "content": "Periodic latency spikes of 500ms+ on Triton model serving. Normal latency is ~20ms. Happens every 30-60 seconds regardless of load. Using dynamic batching with max batch size 32. GPU utilization stays below 50%. No memory leaks detected.",
            "category": "Triton Inference",
            "severity": "medium",
            "status": "open"
        },
        {
            "title": "cuDNN convolution algorithm selection crash",
            "content": "Application crashes when cuDNN auto-tuner selects convolution algorithm. Error: 'CUDNN_STATUS_INTERNAL_ERROR'. Occurs randomly, not reproducible. cuDNN 8.9.5, CUDA 12.2. Workaround: setting CUDNN_BENCHMARK=0 but reduces performance.",
            "category": "cuDNN",
            "severity": "medium",
            "status": "in_progress"
        },
        {
            "title": "DeepStream pipeline drops frames under load",
            "content": "DeepStream 6.3 pipeline processing 16 RTSP streams drops frames when CPU load exceeds 60%. Using nvinfer with custom YOLOv8 model. GPU utilization is only 40%. Suspect bottleneck in demuxer or pre-processing stages.",
            "category": "DeepStream",
            "severity": "medium",
            "status": "open"
        },
        {
            "title": "NIM endpoint returns 503 during peak hours",
            "content": "Self-hosted NIM endpoint becomes unavailable (503 errors) during peak traffic. Deployed on 2x A100 GPUs. Request rate: ~100 req/s. No GPU memory issues visible. Kubernetes HPA not scaling as expected. Suspect connection pool exhaustion.",
            "category": "NVIDIA NIM",
            "severity": "critical",
            "status": "open"
        },
        {
            "title": "Performance regression after driver update to 545",
            "content": "Training throughput dropped 15% after updating driver from 535 to 545. Same code, same hardware (H100 SXM). Verified CUDA version unchanged at 12.2. Power consumption is similar. Issue affects both PyTorch and TensorFlow workloads.",
            "category": "Performance Optimization",
            "severity": "high",
            "status": "open"
        }
    ]


def create_collection(client: MilvusClient):
    """Create the support_tickets collection in Milvus with explicit schema."""
    from pymilvus import DataType
    
    # Drop existing collection if it exists
    if client.has_collection(COLLECTION_NAME):
        print(f"Dropping existing collection: {COLLECTION_NAME}")
        client.drop_collection(COLLECTION_NAME)
    
    # Create schema with explicit fields (required for langchain-milvus retriever)
    print(f"Creating collection: {COLLECTION_NAME}")
    schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field("pk", DataType.VARCHAR, max_length=128, is_primary=True)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
    schema.add_field("text", DataType.VARCHAR, max_length=8192)  # Required field for retriever
    schema.add_field("title", DataType.VARCHAR, max_length=512)
    schema.add_field("category", DataType.VARCHAR, max_length=128)
    schema.add_field("severity", DataType.VARCHAR, max_length=64)
    schema.add_field("status", DataType.VARCHAR, max_length=64)
    
    # Create index params
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="vector", metric_type="L2", index_type="AUTOINDEX")
    
    # Create collection with schema
    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params
    )
    print(f"Collection '{COLLECTION_NAME}' created successfully with explicit schema")


def insert_tickets_with_random_embeddings(client: MilvusClient, tickets: List[Dict]):
    """Insert tickets with random embeddings (for demo without API key)."""
    import random
    
    print(f"Generating random embeddings for {len(tickets)} tickets (demo mode)...")
    
    # Prepare data for insertion with random vectors
    import uuid
    data = []
    for ticket in tickets:
        # Generate random normalized vector for demo
        random_vec = [random.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
        norm = sum(x*x for x in random_vec) ** 0.5
        normalized_vec = [x / norm for x in random_vec]
        
        data.append({
            "pk": str(uuid.uuid4()),  # String primary key
            "vector": normalized_vec,
            "title": ticket["title"][:256],
            "text": f"{ticket['title']}. {ticket['content']}"[:4096],  # Use 'text' field for retriever
            "category": ticket.get("category", "General")[:64],
            "severity": ticket.get("severity", "medium")[:32],
            "status": ticket.get("status", "open")[:32]
        })
    
    print(f"Inserting {len(data)} tickets into Milvus...")
    result = client.insert(collection_name=COLLECTION_NAME, data=data)
    print(f"Inserted {result['insert_count']} tickets successfully")
    return result


def insert_tickets(client: MilvusClient, tickets: List[Dict]):
    """Insert tickets with embeddings into Milvus."""
    # Combine title and content for embedding
    texts = [f"{t['title']}. {t['content']}" for t in tickets]
    
    print(f"Generating embeddings for {len(texts)} tickets...")
    embeddings = generate_embeddings(texts)
    
    # Prepare data for insertion
    import uuid
    data = []
    for i, (ticket, embedding) in enumerate(zip(tickets, embeddings)):
        data.append({
            "pk": str(uuid.uuid4()),  # String primary key
            "vector": embedding,
            "title": ticket["title"][:256],  # Truncate to fit schema
            "text": f"{ticket['title']}. {ticket['content']}"[:4096],  # Use 'text' field for retriever
            "category": ticket.get("category", "General")[:64],
            "severity": ticket.get("severity", "medium")[:32],
            "status": ticket.get("status", "open")[:32]
        })
    
    print(f"Inserting {len(data)} tickets into Milvus...")
    result = client.insert(collection_name=COLLECTION_NAME, data=data)
    print(f"Inserted {result['insert_count']} tickets successfully")
    return result


def test_search(client: MilvusClient, query: str):
    """Test searching the collection."""
    print(f"\nTesting search with query: '{query}'")
    
    # Generate query embedding
    query_embedding = generate_embeddings([query])[0]
    
    # Search
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[query_embedding],
        limit=3,
        output_fields=["title", "text", "category", "severity"]
    )
    
    print(f"Found {len(results[0])} results:")
    for i, hit in enumerate(results[0]):
        print(f"\n  {i+1}. Score: {hit['distance']:.4f}")
        print(f"     Title: {hit['entity']['title']}")
        print(f"     Category: {hit['entity']['category']}")
        print(f"     Severity: {hit['entity']['severity']}")


def main():
    """Main function to seed Milvus with support tickets."""
    print("=" * 60)
    print("AIDP Support Tickets Seeder")
    print("=" * 60)
    
    # Check for API key
    use_synthetic = True
    if not NVIDIA_API_KEY:
        print("\nWarning: NVIDIA_API_KEY environment variable is not set.")
        print("Get an API key from https://build.nvidia.com")
        print("\nProceeding with fallback data (no embeddings - using random vectors)...")
        use_synthetic = False
    
    # Connect to Milvus
    print(f"\nConnecting to Milvus at {MILVUS_URI}...")
    client = MilvusClient(uri=MILVUS_URI)
    print("Connected successfully!")
    
    # Create collection
    create_collection(client)
    
    # Generate or load tickets
    if use_synthetic:
        try:
            tickets = generate_synthetic_tickets(num_tickets=30)
        except Exception as e:
            print(f"LLM generation failed: {e}")
            print("Using fallback tickets...")
            tickets = get_fallback_tickets()
        # Insert with real embeddings
        insert_tickets(client, tickets)
    else:
        # Use fallback data with random embeddings for demo purposes
        tickets = get_fallback_tickets()
        insert_tickets_with_random_embeddings(client, tickets)
    
    # Test search (only works properly with real embeddings)
    if use_synthetic:
        test_search(client, "GPU driver issues after kernel update")
        test_search(client, "memory problems during training")
        test_search(client, "container isolation Kubernetes")
    else:
        print("\nNote: Search test skipped (requires NVIDIA_API_KEY for proper embeddings)")
        print("Set NVIDIA_API_KEY and re-run to enable semantic search.")
    
    print("\n" + "=" * 60)
    print("Seeding complete!")
    print(f"Collection '{COLLECTION_NAME}' now has data ready for RAG queries.")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit(main())

