# Spraay Crypto Payments Agent

An AI agent that executes cryptocurrency payments across 13 blockchains using the [Spraay x402 gateway](https://gateway.spraay.app). The agent can batch-send tokens, create escrow contracts, check balances, get token prices, and hire robots via the Robot Task Protocol (RTP).

## Overview

This example demonstrates how to build a **crypto payment agent** using NeMo Agent Toolkit with custom tools that interact with the Spraay x402 protocol gateway. The agent uses a ReAct pattern to reason about payment tasks and execute them via HTTP API calls.

### What is x402?

The [x402 protocol](https://www.x402.org) enables AI agents to pay for API services using USDC micropayments over HTTP. When an agent calls a paid endpoint, the server returns HTTP 402 (Payment Required) with payment details. The agent signs a USDC transaction, resends the request with the payment proof, and the server executes the operation.

### Supported Chains

Base · Ethereum · Arbitrum · Polygon · BNB Chain · Avalanche · Solana · Bitcoin · Stacks · Unichain · Plasma · BOB · Bittensor

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- NVIDIA API key from [build.nvidia.com](https://build.nvidia.com)

## Setup

1. Clone this repository and navigate to the example:

```bash
cd examples/spraay_crypto_payments
```

2. Install dependencies:

```bash
uv venv --python 3.12 --seed .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
uv pip install nvidia-nat httpx
```

3. Set environment variables:

```bash
export NVIDIA_API_KEY=<your-nvidia-api-key>
export SPRAAY_GATEWAY_URL=https://gateway.spraay.app
```

## Running the Example

### Using the CLI

```bash
nat run --config_file configs/config.yml --input "What chains does Spraay support and what is the current price of ETH on Base?"
```

### Example Prompts

- `"Check the USDC balance for address 0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8 on Base"`
- `"What is the current price of ETH on Base?"`
- `"List all available Spraay gateway routes and their pricing"`
- `"Discover available robots on the RTP network"`

## Architecture

```
┌─────────────────────────────────────────┐
│         NeMo Agent Toolkit              │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │      ReAct Agent (Nemotron)       │  │
│  │                                   │  │
│  │  Tools:                           │  │
│  │  ├── spraay_health                │  │
│  │  ├── spraay_routes                │  │
│  │  ├── spraay_chains                │  │
│  │  ├── spraay_balance               │  │
│  │  ├── spraay_price                 │  │
│  │  ├── spraay_batch_send            │  │
│  │  ├── spraay_escrow_create         │  │
│  │  └── spraay_rtp_discover          │  │
│  └──────────────┬────────────────────┘  │
│                 │                        │
└─────────────────┼────────────────────────┘
                  │ HTTP + x402
                  ▼
     ┌────────────────────────┐
     │  Spraay x402 Gateway   │
     │  gateway.spraay.app    │
     │                        │
     │  76+ paid endpoints    │
     │  13 blockchains        │
     │  USDC micropayments    │
     └────────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `configs/config.yml` | NeMo Agent Toolkit workflow configuration |
| `src/spraay_crypto_payments/spraay_tools.py` | Custom Spraay gateway tools |
| `src/spraay_crypto_payments/__init__.py` | Package init with tool registration |
| `pyproject.toml` | Project dependencies |

## Links

- [Spraay Gateway Docs](https://docs.spraay.app)
- [x402 Protocol](https://www.x402.org)
- [Spraay MCP Server](https://smithery.ai/server/@plagtech/spraay-x402-mcp)
- [NeMo Agent Toolkit Docs](https://docs.nvidia.com/nemo/agent-toolkit/latest/)
- [Spraay on OpenShell](https://github.com/NVIDIA/OpenShell-Community/pull/50)
