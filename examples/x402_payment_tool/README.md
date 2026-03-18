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

AI agents increasingly need to interact with paid APIs and services autonomously. When an agent encounters an HTTP 402 (Payment Required) response, it needs to:

- Evaluate whether the data justifies the cost
- Construct and authorize a payment
- Retry the request with payment proof attached
- Track spending against configurable budget limits

Unlike regular API errors, payment operations are **irreversible** — a bug doesn't just waste a retry, it transfers real value. This requires security guarantees beyond what standard tool integrations provide.

### The Solution

This example demonstrates a payment-enabled tool for NeMo Agent Toolkit that handles [x402](https://github.com/coinbase/x402) payment negotiation within an agent loop. The x402 protocol uses HTTP's previously unused 402 status code to enable machine-to-machine payments.

### How It Works

1. **Agent requests data** from a paid API via the payment tool
2. **API responds with 402** including payment requirements (amount, recipient, token)
3. **Tool evaluates the cost** against the agent's spending policy
4. **Wallet signs the payment** (signing key isolated from the agent process)
5. **Tool retries with payment proof** attached as an HTTP header
6. **Agent receives the data** and continues its task

### Key Security Properties

| Property | Implementation | Why It Matters |
|----------|---------------|----------------|
| **Bounded blast radius** | On-chain spending policies (per-tx cap, daily limit) | A hallucinating LLM cannot drain the wallet |
| **Key isolation** | Wallet signer runs in a separate process | MCP server compromise doesn't leak private keys |
| **Allowlisted recipients** | Only pre-approved addresses can receive payments | Prevents payments to arbitrary addresses |
| **Audit trail** | Every payment logged with tx hash, amount, recipient | Full accountability for autonomous spending |

## Architecture

```
┌─────────────────────────┐
│   NeMo Agent Toolkit    │
│   (ReAct Agent Loop)    │
│                         │
│  ┌───────────────────┐  │
│  │  x402 Payment     │  │     ┌──────────────┐
│  │  Tool             │──┼────▶│  Paid API    │
│  │                   │  │     │  (returns 402)│
│  │  - cost eval      │  │     └──────────────┘
│  │  - budget check   │  │
│  │  - retry w/ proof  │  │
│  └────────┬──────────┘  │
│           │              │
└───────────┼──────────────┘
            │
   ┌────────▼────────┐
   │  Wallet Signer  │
   │  (isolated      │
   │   process)      │
   │                 │
   │  - private key  │
   │  - spend policy │
   │  - tx signing   │
   └─────────────────┘
```

## Prerequisites

- Python >= 3.11
- NeMo Agent Toolkit >= 1.4.0
- An Ethereum wallet with USDC (Base network recommended for low fees)
- Access to an x402-enabled API endpoint (or use the included mock server for testing)

## Quick Start

### 1. Install

```bash
cd examples/x402_payment_tool
pip install -e .
```

### 2. Configure

```bash
# Copy the example config
cp src/nat_x402_payment/configs/payment-agent.example.yml src/nat_x402_payment/configs/payment-agent.yml

# Set your wallet private key (NEVER commit this)
export WALLET_PRIVATE_KEY="your-private-key-here"

# Or use a separate signer process (recommended for production)
export WALLET_SIGNER_URL="http://localhost:8900"
```

### 3. Run with Mock Server (Testing)

```bash
# Start the mock x402 server
python scripts/mock_x402_server.py &

# Run the agent
nat run --config src/nat_x402_payment/configs/payment-agent.yml
```

### 4. Run with Real x402 API

```bash
# Update payment-agent.yml with your x402 API endpoint
nat run --config src/nat_x402_payment/configs/payment-agent.yml
```

## Configuration

### Spending Policy

Edit `configs/payment-agent.yml` to set spending limits:

```yaml
payment_tool:
  max_per_transaction: 0.10    # Max USDC per single payment
  max_daily_spend: 5.00        # Daily spending cap
  allowed_recipients:           # Allowlisted payment recipients
    - "0x..."                   # Your x402 API provider
  require_confirmation: false   # Set true for human-in-the-loop
```

### Wallet Isolation Modes

| Mode | Security | Setup Complexity | Use Case |
|------|----------|-----------------|----------|
| **Inline** | Basic | Low | Development/testing |
| **Separate process** | High | Medium | Production |
| **Hardware signer** | Highest | High | Enterprise |

## Example Output

```
Agent: I need to fetch premium market data for the user's query.
Tool:  Requesting https://api.example.com/v1/market-data?symbol=NVDA
Tool:  Received HTTP 402 — Payment Required
Tool:  Cost: 0.05 USDC | Budget remaining: 4.95 USDC | Policy: APPROVED
Tool:  Payment signed (tx: 0xabc...def) — retrying with proof
Tool:  Data received (200 OK)
Agent: Based on the premium market data, NVDA is currently trading at...
```

## References

- [x402 Protocol (Coinbase)](https://github.com/coinbase/x402) — HTTP 402 payment standard
- [agent-wallet-sdk](https://github.com/up2itnow0822/agent-wallet-sdk) — Non-custodial agent wallets with spending policies
- [agentpay-mcp](https://github.com/up2itnow0822/agentpay-mcp) — MCP payment server implementation
