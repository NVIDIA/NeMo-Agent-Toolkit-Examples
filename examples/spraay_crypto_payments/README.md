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

An AI agent that executes cryptocurrency payments and queries blockchain data
across 15 chains using the [Spraay x402 gateway](https://gateway.spraay.app).
The agent can perform **batch payments to up to 200 recipients in one atomic
transaction**, check balances, get token prices, create escrow contracts, and
discover robotic task execution services.

## Overview

This example demonstrates how to build a crypto payment agent using NeMo
Agent Toolkit with custom tools that interact with the Spraay x402 protocol
gateway. The centerpiece is **batch payments** implementing the
[Batch Payments for Agents (BPA) 1.0](https://docs.spraay.app/bpa/1.0/) spec,
with free validation and estimation endpoints that make the demo fully runnable
in CI without any funded wallet.

### What is x402?

The [x402 protocol](https://www.x402.org) enables AI agents to pay for API
services using USDC micropayments over HTTP. When an agent calls a paid
endpoint, the server returns HTTP 402 (Payment Required) with payment details.
The agent can optionally sign a USDC transaction, resend the request with
payment proof, and the server executes the operation. Without payment
credentials, the agent receives a payment quote (dry-run mode).

### Supported Chains

**Primary:** Base, Ethereum, Solana

**Multi-chain:** Arbitrum, Polygon, Optimism, BNB Chain, Avalanche, Bitcoin,
Stacks, Unichain, Plasma, BOB, Bittensor, Stellar, XRP Ledger

## Tools

All tools are registered in the `spraay` function group and share a single
gateway client.

### Free Tools (No Payment Required)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `spraay__health` | `GET /health` | Gateway health check |
| `spraay__routes` | `GET /.well-known/x402.json` | List all available routes (x402 discovery) |
| `spraay__chains` | `GET /free/chain-status` | List supported blockchains with status |
| `spraay__price` | `GET /free/prices?tokens=...` | Get current token prices |
| `spraay__batch_validate` | `POST /free/validate-batch` | Validate batch payment recipients |
| `spraay__batch_estimate` | `GET /free/estimate-batch` | Estimate gas + fees for batch payment |

### Paid Tools (x402 Protocol, Dry-Run by Default)

| Tool | Endpoint | Price | Description |
|------|----------|-------|-------------|
| `spraay__balance` | `GET /api/v1/balances` | $0.005 | Check token balances for any wallet |
| `spraay__batch_send` | `POST /api/v1/batch/execute` | $0.02 | Execute batch payment to up to 200 recipients |
| `spraay__escrow_create` | `POST /api/v1/escrow/create` | $0.10 | Create escrow contract with conditions |
| `spraay__rtp_discover` | `GET /api/v1/robots/list` | $0.005 | Discover RTP robots by capability/chain/price |

**Paid Tool Modes:**
- **Dry-run (default):** Without `EVM_PRIVATE_KEY` set, paid tools return
  structured payment quotes showing the required USDC amount, network, and
  payment address. Safe for CI and demos.
- **Live mode:** With `EVM_PRIVATE_KEY` set, the agent executes the full x402
  payment flow and receives the actual API result.

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

4. (Optional) For live execution of paid tools, set your EVM private key:

```bash
export EVM_PRIVATE_KEY=<your-private-key>  # NEVER commit or share this
```

**Security note:** The `EVM_PRIVATE_KEY` is only used to sign x402 payment
headers for USDC transfers on Base. It is never logged, echoed, or sent to any
service other than the blockchain. If not set, paid tools operate in dry-run
mode and return payment quotes.

## Sample Runs

### 1. Free Query: Check Supported Chains

```bash
nat run \
  --config_file configs/config.yml \
  --input "What blockchains does Spraay support?"
```

**Output:**

```json
{
  "chains": {
    "base": {
      "chain": "base",
      "name": "Base",
      "chainId": 8453,
      "status": "online"
    },
    "ethereum": {
      "chain": "ethereum",
      "name": "Ethereum",
      "chainId": 1,
      "status": "online"
    },
    "arbitrum": {
      "chain": "arbitrum",
      "name": "Arbitrum One",
      "chainId": 42161,
      "status": "online"
    }
  }
}
```

### 2. Free Query: Get Token Prices

```bash
nat run \
  --config_file configs/config.yml \
  --input "What is the current price of ETH and USDC?"
```

**Output:**

```json
{
  "prices": {
    "ETH": {
      "usd": 1798.01
    },
    "USDC": {
      "usd": 0.999902
    }
  }
}
```

### 3. Free Batch Flow: Validate + Estimate a 3-Recipient USDC Batch

This is the **headline demo** — fully runnable in CI with zero funds required.

**Step 1: Validate**

```bash
nat run \
  --config_file configs/config.yml \
  --input 'Validate a batch payment: send USDC on base to 0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8:1.0, 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb:2.0, 0x8626f6940E2eb28930eFb4CeF49B2d1F2C9C1199:3.0'
```

**Output:**

```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "summary": {
    "chain": "base",
    "token": "USDC",
    "recipientCount": 3,
    "uniqueAddresses": 3,
    "totalAmount": 6.0,
    "bpaVersion": "1.0"
  }
}
```

**Step 2: Estimate Gas + Fees**

```bash
nat run \
  --config_file configs/config.yml \
  --input "Estimate gas for 3 recipients on base with USDC"
```

**Output:**

```json
{
  "estimate": {
    "chain": "base",
    "recipients": 3,
    "protocolFeeBps": 30,
    "estimatedGasUSD": 0.003,
    "bpaVersion": "1.0"
  },
  "note": "Protocol fee: 0.3% of total amount"
}
```

### 4. Dry-Run Paid Tool: Batch Send Payment Quote

Without `EVM_PRIVATE_KEY`, `batch_send` returns the x402 payment quote:

```bash
nat run \
  --config_file configs/config.yml \
  --input "Send 1 USDC on base to 0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8"
```

**Output:**

```json
{
  "mode": "dry_run",
  "endpoint": "/api/v1/batch/execute",
  "payment_required": {
    "price": "$0.020",
    "amount_usdc_raw": 20000,
    "asset": "USDC",
    "network": "eip155:8453",
    "pay_to": "0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8"
  },
  "note": "Set EVM_PRIVATE_KEY environment variable to execute for real."
}
```

### 5. (Optional) Live Mode Snippet

To execute a batch payment for real (requires funded wallet):

```bash
export EVM_PRIVATE_KEY=0x...  # Your funded Base wallet private key
nat run \
  --config_file configs/config.yml \
  --input "Send 1 USDC on base to 0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8"
```

The agent will sign the x402 payment ($0.02 USDC) and execute the batch
transaction, returning the transaction hash and status.

## Architecture

```
NeMo Agent Toolkit
    |
    v
ReAct Agent (Llama 3.1 70B)
    |
    v
spraay function group (shared client)
    |
    +-- spraay__health
    +-- spraay__routes
    +-- spraay__chains
    +-- spraay__price
    +-- spraay__batch_validate (FREE)
    +-- spraay__batch_estimate (FREE)
    +-- spraay__batch_send (PAID $0.02)
    +-- spraay__balance (PAID $0.005)
    +-- spraay__escrow_create (PAID $0.10)
    +-- spraay__rtp_discover (PAID $0.005)
    |
    v
HTTP + x402 Protocol
    |
    v
Spraay x402 Gateway (gateway.spraay.app)
    - 190+ endpoints
    - 15 blockchains
    - USDC micropayments
    - BPA 1.0 batch payments
```

## Files

| File | Description |
|------|-------------|
| `configs/config.yml` | NeMo Agent Toolkit workflow configuration |
| `src/spraay_crypto_payments/register.py` | Tool registration with `@register_function_group` |
| `src/spraay_crypto_payments/spraay_client.py` | Async HTTP client with x402 support |
| `src/spraay_crypto_payments/__init__.py` | Package init |
| `pyproject.toml` | Project dependencies and NAT entry points |

## Related Examples

This example builds on the repository's existing x402 integration work:

- **[x402_payment_tool](../x402_payment_tool/)** (PR #17): Generic x402
  payment negotiation tool where an agent autonomously evaluates a 402 response
  and executes payment. The current example differs by providing domain-specific
  tools (batch payments, escrow, RTP) rather than generic x402 handling.

## Links

- [Spraay Gateway Docs](https://docs.spraay.app)
- [Batch Payments for Agents (BPA) 1.0 Spec](https://docs.spraay.app/bpa/1.0/)
- [x402 Protocol](https://www.x402.org)
- [Spraay MCP Server](https://smithery.ai/server/@plagtech/spraay-x402-mcp)
- [NeMo Agent Toolkit Docs](https://docs.nvidia.com/nemo/agent-toolkit/latest/)
