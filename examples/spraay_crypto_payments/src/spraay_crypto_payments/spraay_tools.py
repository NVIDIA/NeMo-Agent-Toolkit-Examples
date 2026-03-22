# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

"""Spraay x402 Gateway tools for NeMo Agent Toolkit.

These tools enable AI agents to execute cryptocurrency payments across
13 blockchains using the Spraay x402 protocol gateway.
"""

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

GATEWAY_URL = os.environ.get("SPRAAY_GATEWAY_URL", "https://gateway.spraay.app")


async def _gateway_get(path: str, params: dict | None = None) -> dict:
    """Make a GET request to the Spraay gateway."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{GATEWAY_URL}{path}",
            params=params,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()


async def _gateway_post(path: str, data: dict) -> dict:
    """Make a POST request to the Spraay gateway."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GATEWAY_URL}{path}",
            json=data,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()


# ── Free query tools (no x402 payment required) ─────────────────────────────


async def spraay_health() -> str:
    """Check the health status of the Spraay x402 gateway.

    Returns:
        JSON string with gateway health status.
    """
    try:
        result = await _gateway_get("/health")
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def spraay_routes() -> str:
    """List all available Spraay gateway routes with pricing information.

    Returns:
        JSON string with all available routes and their x402 pricing.
    """
    try:
        result = await _gateway_get("/v1/routes")
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def spraay_chains() -> str:
    """List all supported blockchains on the Spraay gateway.

    Returns:
        JSON string with supported chains (Base, Ethereum, Arbitrum,
        Polygon, BNB, Avalanche, Solana, Bitcoin, Stacks, Unichain,
        Plasma, BOB, Bittensor).
    """
    try:
        result = await _gateway_get("/v1/chains")
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def spraay_balance(address: str, chain: str = "base", token: str = "USDC") -> str:
    """Check the token balance of a wallet address on a specific chain.

    Args:
        address: The wallet address to check (e.g., 0x1234...).
        chain: The blockchain to query (default: base).
        token: The token symbol (default: USDC).

    Returns:
        JSON string with the wallet balance.
    """
    try:
        result = await _gateway_get(
            "/v1/balance",
            params={"address": address, "chain": chain, "token": token},
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def spraay_price(token: str, chain: str = "base") -> str:
    """Get the current price of a token on a specific chain.

    Args:
        token: The token symbol (e.g., ETH, USDC, MATIC).
        chain: The blockchain to query (default: base).

    Returns:
        JSON string with the current token price.
    """
    try:
        result = await _gateway_get(
            "/v1/price",
            params={"token": token, "chain": chain},
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Paid action tools (x402 USDC micropayment required) ─────────────────────


async def spraay_batch_send(
    recipients: str,
    token: str = "USDC",
    chain: str = "base",
) -> str:
    """Send tokens to multiple recipients in a single batch transaction.

    This is a PAID endpoint — requires x402 USDC micropayment.

    Args:
        recipients: JSON string of recipients array, each with
            'address' and 'amount' fields.
            Example: '[{"address": "0x...", "amount": "10.0"}]'
        token: The token to send (default: USDC).
        chain: The blockchain to use (default: base).

    Returns:
        JSON string with the transaction result including tx hash.
    """
    try:
        recipients_list = json.loads(recipients)
        result = await _gateway_post(
            "/v1/batch-send",
            data={
                "recipients": recipients_list,
                "token": token,
                "chain": chain,
            },
        )
        return json.dumps(result, indent=2)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid recipients JSON format"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def spraay_escrow_create(
    depositor: str,
    beneficiary: str,
    total_amount: str,
    milestones: str,
    token: str = "USDC",
    chain: str = "base",
) -> str:
    """Create an escrow contract with milestone-based fund releases.

    This is a PAID endpoint — requires x402 USDC micropayment.

    Args:
        depositor: Wallet address of the person depositing funds.
        beneficiary: Wallet address of the person receiving funds.
        total_amount: Total amount to escrow (e.g., "500.0").
        milestones: JSON string of milestones array, each with
            'description' and 'amount' fields.
        token: The token to escrow (default: USDC).
        chain: The blockchain to use (default: base).

    Returns:
        JSON string with the escrow contract details.
    """
    try:
        milestones_list = json.loads(milestones)
        result = await _gateway_post(
            "/v1/escrow/create",
            data={
                "depositor": depositor,
                "beneficiary": beneficiary,
                "totalAmount": total_amount,
                "milestones": milestones_list,
                "token": token,
                "chain": chain,
            },
        )
        return json.dumps(result, indent=2)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid milestones JSON format"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def spraay_rtp_discover(category: str = "") -> str:
    """Discover available robots and IoT devices on the RTP network.

    The Robot Task Protocol (RTP) enables AI agents to hire robots
    and physical devices via x402 USDC micropayments.

    Args:
        category: Optional category filter (e.g., 'robotics',
            'sensing', 'delivery', 'manufacturing', 'compute').

    Returns:
        JSON string with available devices and their capabilities.
    """
    try:
        params = {}
        if category:
            params["category"] = category
        result = await _gateway_get("/v1/rtp/discover", params=params)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
