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

# Agent Identity Verification Tool for NeMo Agent Toolkit

## Overview

### The Problem

As AI agents become more autonomous, they increasingly interact with other agents: delegating subtasks, purchasing services, sharing data. But how does an agent know whether another agent is trustworthy? Without identity verification, agents are vulnerable to impersonation, data poisoning, and unauthorized transactions.

### The Solution

This example implements an agent identity verification tool for NeMo Agent Toolkit using [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) on-chain identity registries. Before your agent transacts with or delegates to another agent, it can verify their identity, check their reputation history, and make a trust decision.

### How It Works

```
Agent needs to interact with another agent
    |
    v
verify_agent_identity called with target address
    |
    v
Tool queries ERC-8004 registry for on-chain identity
    |
    +-- NOT FOUND -> REJECT (no registered identity)
    |
    v
Check reputation score against threshold
    |
    +-- BELOW THRESHOLD -> REJECT (low reputation)
    |
    v
Check required capabilities
    |
    +-- MISSING CAPABILITIES -> REJECT
    |
    v
Check identity status (revoked? expired?)
    |
    +-- REVOKED/EXPIRED -> REJECT
    |
    v
TRUST - safe to interact
```

## What is ERC-8004?

[ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) (Trustless Agents) defines a standard for on-chain AI agent identity using ERC-721 tokens. Each registered agent gets:

- A unique on-chain ID (non-transferable token)
- An agent URI for discovery
- Metadata fields (model, framework, version, capabilities)
- Service endpoint declarations
- A linked reputation registry for feedback and scoring

The identity is non-custodial: agents control their own registration, and the registry is permissionless.

## Best Practices for Agent Identity Verification

### 1. Always Verify Before Transacting

Never send payments, share sensitive data, or accept task results from an unverified agent. The `verify_agent_identity` tool combines identity lookup, reputation check, and capability validation into a single call.

### 2. Set Meaningful Reputation Thresholds

A `min_reputation_score` of 0 accepts any registered agent. For production:

- **Low-risk tasks** (public data queries): 30+
- **Medium-risk tasks** (paid API calls): 60+
- **High-risk tasks** (financial transactions): 80+

### 3. Require Specific Capabilities

If you need a market data provider, set `required_capabilities: ["market-data"]`. This prevents an agent from accepting tasks it cannot fulfill.

### 4. Use Category-Level Reputation

The `lookup_agent_reputation` tool supports filtering by category. An agent might have high accuracy but low reliability. Check the categories that matter for your use case.

## Prerequisites

- Python >= 3.11
- NeMo Agent Toolkit >= 1.4.0 (`pip install nvidia-nat[langchain]`)
- An NVIDIA API key for NIM models (set `NVIDIA_API_KEY`)
- For testing: no blockchain connection needed (mock registry server included)
- For production: access to an ERC-8004 registry on Base, Ethereum, or Arbitrum

## Quick Start

### 1. Install the Example

```bash
cd examples/agent_identity_tool
pip install -e .
```

### 2. Start the Mock Registry Server

```bash
python scripts/mock_registry_server.py &
# Server runs on http://localhost:8500
# GET /identity/<address> -> Agent identity data
# GET /reputation/<address> -> Reputation scores and feedback
# GET /health -> Server status
```

The mock server includes four test agents:

| Agent | Address | Status |
|-------|---------|--------|
| Trusted provider | `0x1234...5678` | Registered, 87.5 reputation |
| Revoked agent | `0xdead...beef` | Revoked, 12.0 reputation |
| Expired agent | `0xaaaa...aaaa` | Expired identity |
| Unknown | `0x0000...0000` | Not registered |

### 3. Configure and Run

```bash
# Copy example config
cp src/nat_agent_identity/configs/identity-agent.example.yml \
   src/nat_agent_identity/configs/identity-agent.yml

# Set NVIDIA API key for the LLM
export NVIDIA_API_KEY="your-nvidia-api-key"

# Run the agent
nat run --config_file src/nat_agent_identity/configs/identity-agent.yml
```

### 4. Test the Agent

Once running, try these prompts:

```
> Verify whether agent 0x1234567890abcdef1234567890abcdef12345678 is trustworthy
```

Expected: TRUST decision with 87.5 reputation score and market-data capabilities.

```
> Check the reputation of 0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef
```

Expected: REJECT decision with 12.0 reputation and revoked identity.

```
> Is 0x0000000000000000000000000000000000000000 a registered agent?
```

Expected: REJECT with "No on-chain identity found."

## File Structure

```
agent_identity_tool/
+-- README.md
+-- pyproject.toml
+-- scripts/
|   +-- mock_registry_server.py     # Mock ERC-8004 registry for testing
+-- src/nat_agent_identity/
    +-- __init__.py
    +-- register.py                  # NAT tool registration (@register_function)
    +-- configs/
        +-- identity-agent.example.yml  # NAT workflow configuration
```

## Configuration Reference

### `verify_agent_identity`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `registry_url` | `http://localhost:8500` | Identity registry service URL |
| `min_reputation_score` | 0.0 | Minimum reputation score (0-100) for trust |
| `required_capabilities` | [] | Capabilities the agent must advertise |
| `chain` | `base` | Target chain for identity queries |
| `request_timeout` | 15.0 | HTTP timeout in seconds |

### `lookup_agent_reputation`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `registry_url` | `http://localhost:8500` | Reputation registry service URL |
| `chain` | `base` | Target chain for reputation queries |
| `request_timeout` | 15.0 | HTTP timeout in seconds |

## Production Setup

For production deployments, point `registry_url` at a service backed by [`agentwallet-sdk`](https://github.com/up2itnow0822/agent-wallet-sdk), which provides full ERC-8004 registry clients for identity resolution, reputation queries, and validation.

```bash
npm install agentwallet-sdk
```

```typescript
import { ERC8004Client, ReputationClient } from 'agentwallet-sdk/identity';

const identity = new ERC8004Client({ chain: 'base' });
const reputation = new ReputationClient({ chain: 'base' });

// Look up an agent
const agent = await identity.resolve('0x1234...');
const rep = await reputation.getSummary(agent.agentId);
```

## Combining with x402 Payments

This tool pairs naturally with the [x402 payment tool](../x402_payment_tool/). Before paying an agent for a service:

1. Use `verify_agent_identity` to confirm the agent's on-chain identity
2. Check their reputation meets your threshold
3. Verify they advertise the capability you need
4. Then use `fetch_paid_api` to pay for their service

This creates a trust-then-transact pattern where agents only send funds to verified, reputable counterparties.

## References

- [ERC-8004: Trustless Agents](https://eips.ethereum.org/EIPS/eip-8004) - On-chain agent identity standard
- [agentwallet-sdk](https://github.com/up2itnow0822/agent-wallet-sdk) - ERC-8004 client implementation with identity, reputation, and validation registries
- [x402 Payment Tool](../x402_payment_tool/) - Companion payment tool for NeMo Agent Toolkit
