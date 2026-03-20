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

# x402 Payment Tool for NeMo Agent Toolkit

## Overview

### The Problem

AI agents increasingly need to interact with paid APIs and services. When an agent encounters an HTTP 402 (Payment Required) response, it needs to evaluate the cost, authorize payment, and retry — all autonomously. Unlike regular API errors, payment operations are **irreversible**, requiring security guarantees beyond standard tool integrations.

### The Solution

This example implements a payment-enabled tool for NeMo Agent Toolkit using `@register_function` that handles [x402](https://github.com/coinbase/x402) payment negotiation within a ReAct agent loop.

### How It Works

```
Agent receives user query
    │
    ▼
fetch_paid_api tool called with target URL
    │
    ▼
API responds with HTTP 402 + x402 payment requirements
    │
    ▼
Tool checks spending policy (per-tx cap, daily limit, recipient allowlist)
    │
    ├── DENIED → Return denial reason to agent
    │
    ▼
Wallet signer (isolated process) signs the payment
    │
    ▼
Tool retries request with X-PAYMENT header
    │
    ▼
Agent receives data and continues reasoning
```

## Best Practices for x402 Payment Tools

### 1. Isolate Wallet Keys from the Agent Process

Payment tools handle irreversible value transfer. The signing key must never live in the same process as the agent.

| Mode | Key Location | Use Case |
|------|-------------|----------|
| **Inline** (dev only) | `WALLET_PRIVATE_KEY` environment variable | Local testing with mock server |
| **Remote signer** (production) | Separate process via `WALLET_SIGNER_URL` | Any deployment with real funds |

The remote signer pattern ensures that even if the agent process is compromised, the attacker cannot sign arbitrary transactions — the signer only accepts pre-validated payment requests.

### 2. Enforce Spending Policy Before Signing

Spending limits are checked **before** the wallet is asked to sign, not after. This prevents a compromised or hallucinating agent from constructing valid payment transactions that exceed budget.

```yaml
# In your NAT workflow config:
functions:
  fetch_paid_api:
    _type: fetch_paid_api
    max_per_transaction: 0.10    # Max USDC per payment
    max_daily_spend: 5.00        # Daily cap
    allowed_recipients:           # Only these addresses can receive funds
      - "0x..."
```

### 3. Allowlist Payment Recipients

Never allow an agent to pay arbitrary addresses. Configure `allowed_recipients` with the addresses of your known API providers. Any payment to an unlisted address is rejected before signing.

### 4. Log Every Payment Attempt

The `get_payment_status` tool provides the agent with spending awareness and gives operators a full audit trail. Every payment attempt (successful, denied, or failed) is logged with timestamp, amount, recipient, and transaction hash.

## Prerequisites

- Python >= 3.11
- NeMo Agent Toolkit >= 1.4.0 (`pip install nvidia-nat[langchain]`)
- An NVIDIA API key for NIM models (set `NVIDIA_API_KEY`)
- For testing: no wallet needed (mock server accepts any signature)
- For production: an Ethereum wallet with USDC on Base network

## Quick Start

### 1. Install the Example

```bash
cd examples/x402_payment_tool
pip install -e .
```

### 2. Start the Mock x402 Server

```bash
python scripts/mock_x402_server.py &
# Server runs on http://localhost:8402
# GET /v1/market-data → 402 (requires payment)
# GET /v1/market-data + X-PAYMENT header → 200 (mock data)
```

### 3. Configure and Run

```bash
# Copy example config
cp src/nat_x402_payment/configs/payment-agent.example.yml \
   src/nat_x402_payment/configs/payment-agent.yml

# Set wallet key (any hex string works with mock server)
export WALLET_PRIVATE_KEY="0x0000000000000000000000000000000000000000000000000000000000000001"

# Set NVIDIA API key for the LLM
export NVIDIA_API_KEY="your-nvidia-api-key"

# Run the agent
nat run --config_file src/nat_x402_payment/configs/payment-agent.yml
```

### 4. Test the Agent

Once the agent is running, try prompts like:

```
> Fetch the premium market data from http://localhost:8402/v1/market-data
```

The agent will:
1. Call `fetch_paid_api` with the URL
2. Receive a 402 response
3. Evaluate the cost (0.05 USDC) against the spending policy
4. Sign payment and retry
5. Return the market data

```
> What's my current payment spending status?
```

The agent will call `get_payment_status` and report daily spend and recent transactions.

## File Structure

```
x402_payment_tool/
├── README.md
├── pyproject.toml
├── scripts/
│   └── mock_x402_server.py          # Mock paid API for testing
└── src/nat_x402_payment/
    ├── __init__.py
    ├── register.py                   # NAT tool registration (@register_function)
    ├── wallet.py                     # Wallet signing abstraction (inline/remote)
    └── configs/
        └── payment-agent.example.yml # NAT workflow configuration
```

## Configuration Reference

### Spending Policy

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_per_transaction` | 0.10 | Maximum USDC per single payment |
| `max_daily_spend` | 5.00 | Daily spending cap in USDC |
| `allowed_recipients` | [] | Allowlisted addresses (empty = allow all) |
| `wallet_signer_url` | "" | Remote signer URL (empty = inline mode) |
| `request_timeout` | 30.0 | HTTP request timeout in seconds |

### Wallet Modes

**Inline (development):**
```bash
export WALLET_PRIVATE_KEY="0x..."
```

**Remote signer (production):**
```yaml
functions:
  fetch_paid_api:
    _type: fetch_paid_api
    wallet_signer_url: "http://localhost:8900"
```

The remote signer exposes three endpoints:
- `GET /address` — wallet public address
- `GET /balance?asset=...&network=...` — token balance
- `POST /sign` — sign a payment request

## References

- [x402 Protocol (Coinbase)](https://github.com/coinbase/x402) — HTTP 402 payment standard
- [agent-wallet-sdk](https://github.com/up2itnow0822/agent-wallet-sdk) — Non-custodial agent wallets with on-chain spending policies
- [agentpay-mcp](https://github.com/up2itnow0822/agentpay-mcp) — MCP payment server implementation
- Related issue: [NVIDIA/NeMo-Agent-Toolkit#1806](https://github.com/NVIDIA/NeMo-Agent-Toolkit/issues/1806)
