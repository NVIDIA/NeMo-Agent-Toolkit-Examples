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
credentials, an x402 client receives a payment quote instead of the result
(dry-run mode).

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

### Paid Tools (x402 Protocol — Require `EVM_PRIVATE_KEY`)

The paid tools register **only when `EVM_PRIVATE_KEY` is set**. Without the key
they are not exposed to the agent at all, so this example is safe to run in CI
with no wallet.

| Tool | Endpoint | Price | Description |
|------|----------|-------|-------------|
| `spraay__balance` | `GET /api/v1/balances` | $0.005 | Check token balances for any wallet |
| `spraay__batch_send` | `POST /api/v1/batch/execute` | $0.02 | Execute batch payment to up to 200 recipients |
| `spraay__escrow_create` | `POST /api/v1/escrow/create` | $0.10 | Create escrow contract with conditions |
| `spraay__rtp_discover` | `GET /api/v1/robots/list` | $0.005 | Discover RTP robots by capability/chain/price |

**Tool registration modes:**
- **Free-only (default):** Without `EVM_PRIVATE_KEY` set, only the six free
  tools above register. The paid tools are not exposed to the agent, so no
  wallet, signing, or funds are involved — safe for CI and demos. To preview a
  batch payment with zero funds, use the free `batch_validate` and
  `batch_estimate` tools.
- **Full set (with key):** With `EVM_PRIVATE_KEY` set, the four paid tools
  register alongside the free ones. Paid requests are then routed through the
  [x402 SDK](https://pypi.org/project/x402/) payment transport: when the gateway
  returns `402 Payment Required` (x402Version 2), the SDK signs an EIP-3009
  `TransferWithAuthorization` for USDC on Base (the `exact` scheme), attaches it
  as the `X-PAYMENT` header, and retries. The gateway's facilitator settles the
  USDC transfer on-chain and returns the real API result together with an
  `X-PAYMENT-RESPONSE` header containing the settlement transaction hash
  (surfaced in the tool output under `settlement`). **This moves real funds** —
  `spraay__batch_send` broadcasts a real batch payment to every recipient in the
  list. Preview with the free `batch_validate` / `batch_estimate` tools and test
  with a single small recipient first.

## Prerequisites

- Python 3.11+
- NeMo Agent Toolkit >= 1.4.0 (`pip install nvidia-nat[langchain]`)
- NVIDIA API key from [NVIDIA build portal](https://build.nvidia.com)

## Setup

1. Clone this repository and navigate to the example:

```bash
cd examples/spraay_crypto_payments
```

2. Install dependencies:

```bash
pip install -e .
```

3. Set environment variables:

```bash
export NVIDIA_API_KEY=<your-nvidia-api-key>
export SPRAAY_GATEWAY_URL=https://gateway.spraay.app  # optional, this is the default
```

4. (Optional) To register and live-execute the paid tools, set your EVM private
   key. Without it, only the six free tools register:

```bash
export EVM_PRIVATE_KEY=<your-private-key>  # NEVER commit or share this
```

**Security note:** The `EVM_PRIVATE_KEY` is only used to sign x402 payment
headers for USDC transfers on Base. It is never logged, echoed, or sent to any
service other than the blockchain. If not set, the paid tools are not
registered and only the free tools are available.

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
    // ... additional chains omitted (Polygon, Optimism, Avalanche,
    // BNB Chain, and others); the live gateway returns all supported chains
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

### 4. (Optional) Live Mode — Moves Real Funds

> ⚠️ **Live mode moves real money.** With `EVM_PRIVATE_KEY` set, `batch_send`
> broadcasts a real USDC batch payment to every recipient, and the x402 gateway
> fee ($0.02 for batch send) is charged as a real USDC transfer on Base. Use a
> dedicated wallet funded with only what you intend to spend. Test with a
> single small recipient first.

To execute a batch payment for real, set a **funded** Base wallet key and run
the batch-send input directly (bypassing the agent's tool selection so exactly
one payment is attempted):

```bash
export EVM_PRIVATE_KEY=0x...  # Funded Base wallet; never commit or share this
nat run \
  --config_file configs/config.yml \
  --input 'Use the batch_send tool with this exact JSON: {"recipients":[{"to":"0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8","amount":"0.01"}],"token":"USDC","chain":"base","sender":"0xYOUR_FUNDED_WALLET_ADDRESS"}'
```

Set `sender` to the public address of the wallet derived from `EVM_PRIVATE_KEY`
(the batch tool otherwise fills in a zero-address placeholder that is only valid
for dry-run quotes).

What happens under the hood:

1. The gateway responds `402 Payment Required` (x402Version 2) with the USDC
   `exact` payment terms on Base (`eip155:8453`).
2. The x402 SDK signs an EIP-3009 `TransferWithAuthorization` for the fee using
   your key, resends the request with the `X-PAYMENT` header, and the gateway's
   facilitator settles it on-chain.
3. The tool returns the settled API result plus a `settlement` object with the
   transaction hash.

If the wallet holds insufficient USDC, the gateway rejects the payment and the
tool returns a structured `mode: live` error explaining why — no partial charge.

**Requirements for a successful live run:**

- The paying wallet (derived from `EVM_PRIVATE_KEY`) must hold USDC on Base to
  cover both the gateway fee and the amounts being sent to recipients.
- Install the live-mode dependencies (included by `pip install -e .`, which
  pulls `x402[evm,httpx]`).

#### Deterministic first live test (no agent, no LLM)

For the most predictable first live run, use the standalone `batch_send` smoke
script, which lives in the Spraay gateway repo:
[`scripts/live_batch_send_smoke.py`](https://github.com/plagtech/spraay-x402-gateway/blob/main/scripts/live_batch_send_smoke.py).
It drives `batch_send` directly through the client — no ReAct agent, no
`NVIDIA_API_KEY`, and exactly one payment attempt — and requires you to type
`yes` before moving funds. It derives `sender` from your key automatically,
prints a summary, prompts for confirmation (skip with `--yes`), and reports the
settlement transaction hash. Run it first with no key (dry-run quote), then with
a funded `EVM_PRIVATE_KEY`. See its `--help` for multi-recipient
(`--to addr:amount`), token, chain, and gateway options.

#### Verified live run

A real run of this smoke test against the production gateway
(`gateway.spraay.app`) — the flat batch payload parsed correctly and the x402
gateway fee settled on **Base mainnet** (`eip155:8453`):

```text
================================================================
Spraay batch_send smoke test
================================================================
  mode        : LIVE (moves real funds)
  gateway     : https://gateway.spraay.app
  token/chain : USDC on base
  sender      : 0x6dc474a4EC7Bc5eA509755179317F3d95B93dc91
  recipients  : 1
      -> 0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8  0.33 USDC
  total send  : 0.33 USDC (plus the $0.02 x402 gateway fee)
================================================================
This will move REAL funds. Type 'yes' to proceed: yes

Submitting batch to https://gateway.spraay.app/api/v1/batch/execute ...

{
  "mode": "live",
  "result": {
    "success": true,
    "contract": "0x1646452F98E36A3c9Cfc3eDD8868221E207B5eEC",
    "token": {
      "symbol": "USDC",
      "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      "decimals": 6,
      "isETH": false
    },
    "batch": {
      "recipientCount": 1,
      "totalAmount": "0.33",
      "fee": "0.00099",
      "feePercent": "0.3%",
      "totalWithFee": "0.33099"
    },
    "transaction": {
      "to": "0x1646452F98E36A3c9Cfc3eDD8868221E207B5eEC",
      "data": "0xfb83b683000000000000000000000000833589fcd6edb6e08f4c7c32d4f71b54bda0291300000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000001000000000000000000000000ad62f03c7514bb8c51f1ea70c2b75c37404695c80000000000000000000000000000000000000000000000000000000000050910",
      "value": "0",
      "chainId": 8453
    },
    "approvalRequired": {
      "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      "spender": "0x1646452F98E36A3c9Cfc3eDD8868221E207B5eEC",
      "amount": "330990",
      "amountFormatted": "0.33099"
    }
  },
  "settlement": {
    "success": true,
    "payer": "0x6dc474a4EC7Bc5eA509755179317F3d95B93dc91",
    "transaction": "0x4a3fdb079beb6b87ca0798b4e6be98496f45fffaed8ed0227987e0c1af54fdd7",
    "network": "eip155:8453"
  }
}
```

Verify on-chain:
<https://basescan.org/tx/0x4a3fdb079beb6b87ca0798b4e6be98496f45fffaed8ed0227987e0c1af54fdd7>

The `$0.02` fee is the x402 charge for `/api/v1/batch/execute`; the batch itself
is returned as non-custodial calldata for the sender to broadcast.

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
