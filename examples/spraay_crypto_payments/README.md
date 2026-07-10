<!--
SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# Spraay Crypto Payments Agent

An AI agent that queries cryptocurrency data across 15 blockchains using the
[Spraay x402 gateway](https://gateway.spraay.app). The agent can check gateway
health, list supported chains and routes, look up wallet balances, and get
token prices - all through natural language.

## Overview

This example demonstrates how to build a crypto query agent using NeMo
Agent Toolkit with custom tools that interact with the Spraay x402 protocol
gateway. The agent uses a ReAct pattern to reason about queries and execute
them via HTTP API calls.

### What is x402?

The [x402 protocol](https://www.x402.org) enables AI agents to pay for API
services using USDC micropayments over HTTP. When an agent calls a paid
endpoint, the server returns HTTP 402 (Payment Required) with payment details.
The agent signs a USDC transaction, resends the request with payment proof,
and the server executes the operation.

### Supported Chains

Base, Ethereum, Arbitrum, Polygon, BNB Chain, Avalanche, Solana,
Bitcoin, Stacks, Unichain, Plasma, BOB, Bittensor, Stellar, XRP Ledger.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- NVIDIA API key from [NVIDIA build portal](https://build.nvidia.com)

## Setup

1. Clone this repository and navigate to the example:

```bash
cd examples/spraay_crypto_payments
```

2. Install dependencies:

```bash
uv pip install -e .
```

3. Set environment variables:

```bash
export NVIDIA_API_KEY=<your-nvidia-api-key>
export SPRAAY_GATEWAY_URL=https://gateway.spraay.app  # optional, this is the default
```

## Running the Example

### Check gateway health

```bash
nat run \
  --config_file configs/config.yml \
  --input "Is the Spraay gateway healthy?"
```

### List supported chains

```bash
nat run \
  --config_file configs/config.yml \
  --input "What blockchains does Spraay support?"
```

### Get token price

```bash
nat run \
  --config_file configs/config.yml \
  --input "What is the current price of ETH on Base?"
```

## Expected Output

```
$ nat run --config_file configs/config.yml --input "Is the Spraay gateway healthy?"

Configuration Summary:
--------------------
Workflow Type: react_agent
Number of Functions: 5
Number of LLMs: 1

Agent's thoughts:
Thought: The user wants to check if the Spraay gateway is healthy.
I should use the spraay__health tool.
Action: spraay__health
Action Input: check health

Observation: {
  "status": "ok",
  "version": "3.6.0",
  "uptime": "..."
}

Thought: The gateway is healthy and running.
Final Answer: Yes, the Spraay x402 gateway is healthy. It is running
version 3.6.0 and reporting an "ok" status.
------------------------------
Workflow Result: ['Yes, the Spraay x402 gateway is healthy...']
```

## Architecture

```
NeMo Agent Toolkit
    |
    v
ReAct Agent (Llama 3.1)
    |
    v
spraay function group (shared client)
    |
    +-- spraay__health
    +-- spraay__routes
    +-- spraay__chains
    +-- spraay__balance
    +-- spraay__price
    |
    v
HTTP + x402
    |
    v
Spraay x402 Gateway (gateway.spraay.app)
    - 84+ paid endpoints
    - 15 blockchains
    - USDC micropayments
```

## Files

| File | Description |
|------|-------------|
| `configs/config.yml` | NeMo Agent Toolkit workflow configuration |
| `src/spraay_crypto_payments/register.py` | Tool registration with `@register_function_group` |
| `src/spraay_crypto_payments/spraay_client.py` | Async HTTP client for the Spraay gateway |
| `src/spraay_crypto_payments/__init__.py` | Package init |
| `pyproject.toml` | Project dependencies and NAT entry points |

## Links

- [Spraay Gateway Docs](https://docs.spraay.app)
- [x402 Protocol](https://www.x402.org)
- [Spraay MCP Server](https://smithery.ai/server/@plagtech/spraay-x402-mcp)
- [NeMo Agent Toolkit Docs](https://docs.nvidia.com/nemo/agent-toolkit/latest/)
