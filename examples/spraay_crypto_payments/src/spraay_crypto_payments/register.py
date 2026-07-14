# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
"""Spraay x402 Gateway tools - NeMo Agent Toolkit registration.

Registers the Spraay gateway tools as a single function group so that all
tools share one Spraay client instance. The group is referenced by _type in
the function_groups section of a workflow config.yml.
"""

import logging
import os

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function import FunctionGroup
from nat.cli.register_workflow import register_function_group
from nat.data_models.function import FunctionGroupBaseConfig

from .spraay_client import SpraayClient
from .spraay_client import to_batch_execute_payload

logger = logging.getLogger(__name__)


class SpraayToolsGroupConfig(FunctionGroupBaseConfig, name="spraay"):
    """Configuration for the Spraay x402 gateway function group.

    All tools in this group share a single SpraayClient, pointed at the
    configured gateway URL.
    """

    gateway_url: str = Field(
        default="https://gateway.spraay.app",
        description="Base URL of the Spraay x402 gateway",
    )


@register_function_group(config_type=SpraayToolsGroupConfig)
async def spraay(config: SpraayToolsGroupConfig, _builder: Builder):
    """Register the Spraay gateway tools as a group sharing one client."""

    # One shared client for every tool in the group.
    client = SpraayClient(gateway_url=config.gateway_url)

    group = FunctionGroup(config=config)

    async def health(query: str = "") -> str:
        """Check the health status of the Spraay x402 gateway.

        This is a free query - no x402 USDC payment is required.

        Args:
            query: Unused; the endpoint is fixed. Provided for agent compatibility.

        Returns:
            JSON string with the gateway health status.
        """
        return await client.get("/health")

    async def routes(query: str = "") -> str:
        """List all available Spraay gateway routes with pricing info.

        This is a free query - no x402 USDC payment is required.

        Args:
            query: Unused; the endpoint is fixed. Provided for agent compatibility.

        Returns:
            JSON string with a compact summary of gateway routes (x402 discovery manifest).
        """
        import json as json_mod
        result = await client.get("/.well-known/x402.json")
        try:
            # Return compact summary to keep agent context small
            data = json_mod.loads(result)
            resources = data.get("resources", [])
            summary = {
                "total_resources": len(resources),
                "supported_chains": data.get("supportedChains", []),
                "network": data.get("network"),
                "sample_resources": resources[:10],  # First 10
                "note": f"Showing 10 of {len(resources)} resources. Full manifest at /.well-known/x402.json",
            }
            return json_mod.dumps(summary, indent=2)
        except Exception:
            return result  # Return raw if parsing fails

    async def chains(query: str = "") -> str:
        """List all supported blockchains on the Spraay gateway.

        This is a free query - no x402 USDC payment is required.

        Args:
            query: Unused; the endpoint is fixed. Provided for agent compatibility.

        Returns:
            JSON string with the list of supported chains and their status.
        """
        return await client.get("/free/chain-status")

    async def balance(query: str) -> str:
        """Check the token balance of a wallet address on a specific blockchain.

        This is a PAID endpoint ($0.005 via x402).
        - Without EVM_PRIVATE_KEY: returns payment quote (dry-run). No funds move.
        - With EVM_PRIVATE_KEY: pays the $0.005 fee as a real USDC transfer on
          Base (x402 exact scheme) and returns the balance.

        Args:
            query: A string containing the wallet address and optionally
                the chain and token, e.g.:
                '0xAd62...c8 on base for USDC'
                '0xAd62...c8' (defaults to Base/USDC)

        Returns:
            JSON string with the wallet balance or payment quote.
        """
        parts = query.strip().split()
        address = parts[0] if parts else query.strip()
        chain = "base"
        token = "USDC"

        lower_parts = [p.lower() for p in parts]
        if "on" in lower_parts:
            idx = lower_parts.index("on")
            if idx + 1 < len(parts):
                chain = parts[idx + 1].lower()
        if "for" in lower_parts:
            idx = lower_parts.index("for")
            if idx + 1 < len(parts):
                token = parts[idx + 1].upper()

        return await client.get(
            "/api/v1/balances",
            params={
                "address": address, "chain": chain, "token": token
            },
        )

    async def price(query: str) -> str:
        """Get the current price of a token on a specific blockchain.

        This is a free query - no x402 USDC payment is required.

        Args:
            query: A string containing the token symbol(s), e.g.:
                'ETH'
                'ETH,USDC,SOL' (comma-separated for multiple tokens)

        Returns:
            JSON string with the current token price(s).
        """
        # Parse tokens from query (comma-separated or space-separated)
        tokens = query.strip().replace(" ", ",").upper()
        if not tokens:
            tokens = "ETH,USDC"

        return await client.get(
            "/free/prices",
            params={"tokens": tokens},
        )

    async def batch_validate(query: str) -> str:
        """Validate a batch payment recipient list before sending.

        This is a FREE endpoint - no x402 payment required. Use this to check
        recipient addresses, amounts, and batch structure before executing.

        Args:
            query: JSON string or natural language describing the batch, e.g.:
                '{"recipients":[{"to":"0xAd62...","amount":"1.5"}],"token":"USDC","chain":"base"}'
                'validate sending USDC on base to 0xAd62...:1.5, 0xDef...:2.0'

        Returns:
            JSON string with validation results (valid, errors, warnings, summary).
        """
        import json as json_mod
        try:
            # Try parsing as JSON first
            data = json_mod.loads(query)
        except Exception:
            # Parse natural language: "validate sending USDC on base to addr1:amt1, addr2:amt2"
            parts = query.lower().replace("validate", "").replace("sending", "").strip().split()
            token = "USDC"
            chain = "base"
            recipients = []

            # Extract token and chain
            for i, part in enumerate(parts):
                if part.upper() in ["USDC", "ETH", "DAI"]:
                    token = part.upper()
                elif part == "on" and i + 1 < len(parts):
                    chain = parts[i + 1]
                elif part == "to" and i + 1 < len(parts):
                    # Parse "addr1:amt1, addr2:amt2"
                    recipient_str = " ".join(parts[i + 1:])
                    for rec in recipient_str.split(","):
                        if ":" in rec:
                            addr, amt = rec.strip().split(":")
                            recipients.append({"to": addr.strip(), "amount": amt.strip()})
                    break

            data = {"recipients": recipients, "token": token, "chain": chain}

        return await client.post("/free/validate-batch", data)

    async def batch_estimate(query: str) -> str:
        """Estimate gas and total cost for a batch payment before executing.

        This is a FREE endpoint - no x402 payment required. Returns protocol
        fee (0.3%), estimated gas in USD, and total cost breakdown.

        Args:
            query: Query string with recipient count, chain, and token, e.g.:
                'recipients=3&chain=base&token=USDC'
                'estimate 5 recipients on base with USDC'

        Returns:
            JSON string with cost estimate (gas, fees, total).
        """
        # Parse query into parameters
        params = {}
        if "=" in query and "&" in query:
            # Direct parameter format
            for param in query.split("&"):
                if "=" in param:
                    key, val = param.split("=", 1)
                    params[key.strip()] = val.strip()
        else:
            # Natural language: "estimate 5 recipients on base with USDC"
            parts = query.split()
            params = {"chain": "base", "token": "USDC"}
            for i, part in enumerate(parts):
                if part.isdigit():
                    params["recipients"] = part
                elif part == "on" and i + 1 < len(parts):
                    params["chain"] = parts[i + 1]
                elif part.upper() in ["USDC", "ETH", "DAI"]:
                    params["token"] = part.upper()

        return await client.get("/free/estimate-batch", params)

    async def batch_send(query: str) -> str:
        """Execute a batch payment to up to 200 recipients in one atomic transaction.

        This is a PAID endpoint ($0.02 via x402). Implements BPA 1.0 spec.
        - Without EVM_PRIVATE_KEY: returns a payment quote only (dry-run). No
          funds move.
        - With EVM_PRIVATE_KEY: MOVES REAL FUNDS. Signs the $0.02 x402 gateway
          fee as a USDC EIP-3009 transfer on Base, submits the batch, and the
          gateway broadcasts a real payment to every recipient in the list. The
          result includes the settlement transaction hash under "settlement".

        Supports Base, Ethereum, Solana, and other chains. Protocol fee: 0.3%.

        Args:
            query: JSON or natural language describing the batch, e.g.:
                'send USDC on base to 0xAd62...:1.5, 0xDef...:2.0'
                '{"recipients":[{"to":"0x...","amount":"1.5"}],"token":"USDC","chain":"base","sender":"0x..."}'

        Returns:
            JSON string with transaction result or payment quote.
        """
        import json as json_mod
        try:
            # Try parsing as JSON first
            data = json_mod.loads(query)
        except Exception:
            # Parse natural language: "send USDC on base to addr1:amt1, addr2:amt2"
            parts = query.lower().replace("send", "").strip().split()
            token = "USDC"
            chain = "base"
            recipients = []

            # Extract token and chain
            for i, part in enumerate(parts):
                if part.upper() in ["USDC", "ETH", "DAI", "SOL"]:
                    token = part.upper()
                elif part == "on" and i + 1 < len(parts):
                    chain = parts[i + 1]
                elif part == "to" and i + 1 < len(parts):
                    # Parse "addr1:amt1, addr2:amt2"
                    recipient_str = " ".join(parts[i + 1:])
                    for rec in recipient_str.split(","):
                        if ":" in rec:
                            addr, amt = rec.strip().split(":")
                            recipients.append({"to": addr.strip(), "amount": amt.strip()})
                    break

            data = {"recipients": recipients, "token": token, "chain": chain}

        # Add sender field if not present (required by BPA 1.0 spec)
        if "sender" not in data:
            data["sender"] = "0x0000000000000000000000000000000000000000"  # Placeholder for dry-run

        # The paid execute endpoint requires parallel recipients/amounts arrays
        # in raw base units (see its 402 bazaar schema), not the {to, amount}
        # decimal objects the free validate/estimate endpoints accept.
        payload = to_batch_execute_payload(data)

        return await client.post("/api/v1/batch/execute", payload)

    async def escrow_create(query: str) -> str:
        """Create an escrow contract for conditional payment release.

        This is a PAID endpoint ($0.10 via x402).
        - Without EVM_PRIVATE_KEY: returns payment quote (dry-run). No funds move.
        - With EVM_PRIVATE_KEY: pays the $0.10 fee as a real USDC transfer on
          Base (x402 exact scheme) and creates the escrow.

        Args:
            query: JSON describing the escrow, e.g.:
                '{"amount":"100","token":"USDC","chain":"base","beneficiary":"0x...","condition":"api_verified"}'

        Returns:
            JSON string with escrow contract details or payment quote.
        """
        import json as json_mod
        try:
            data = json_mod.loads(query)
        except Exception:
            return json_mod.dumps(
                {"error": "Invalid escrow format. Expected JSON with amount, token, chain, beneficiary, condition."})

        return await client.post("/api/v1/escrow/create", data)

    async def rtp_discover(query: str) -> str:
        """Discover available RTP (Robot Task Protocol) robots.

        This is a PAID endpoint ($0.005 via x402). Filter by capability,
        chain, price range, or status.
        - Without EVM_PRIVATE_KEY: returns payment quote (dry-run). No funds move.
        - With EVM_PRIVATE_KEY: pays the $0.005 fee as a real USDC transfer on
          Base (x402 exact scheme) and returns the robot list.

        Args:
            query: Filter query, e.g.:
                'capability=pick&chain=base'
                'find robots with pick capability under $5'

        Returns:
            JSON string with available robots or payment quote.
        """
        # Parse query into parameters
        params = {}
        if "=" in query and "&" in query:
            # Direct parameter format
            for param in query.split("&"):
                if "=" in param:
                    key, val = param.split("=", 1)
                    params[key.strip()] = val.strip()
        else:
            # Natural language parsing
            parts = query.lower().split()
            for i, part in enumerate(parts):
                if "pick" in part or "place" in part:
                    params["capability"] = part
                elif part == "under" and i + 1 < len(parts):
                    # Extract price like "$5" or "5"
                    price_str = parts[i + 1].replace("$", "")
                    params["max_price"] = price_str

        return await client.get("/api/v1/robots/list", params)

    # Paid tools move real USDC, so they are only exposed when an EVM signing
    # key is configured. NAT's per-function ``filter_fn`` is the idiomatic hook
    # for conditional membership: the function is added to the group, but the
    # group filters it out of every accessor unless the predicate passes. Here
    # the predicate is a constant captured at build time (EVM_PRIVATE_KEY set),
    # so paid tools simply do not appear in the agent's toolset without a key.
    paid_tools_enabled = bool(os.environ.get("EVM_PRIVATE_KEY"))

    async def _requires_evm_key(_name: str) -> bool:
        return paid_tools_enabled

    if not paid_tools_enabled:
        logger.info("EVM_PRIVATE_KEY not set; registering free Spraay tools only. Paid "
                    "tools (balance, batch_send, escrow_create, rtp_discover) are "
                    "skipped. Set EVM_PRIVATE_KEY to enable them.")

    # Free info & discovery tools (always registered).
    group.add_function("health", health, description=health.__doc__)
    group.add_function("routes", routes, description=routes.__doc__)
    group.add_function("chains", chains, description=chains.__doc__)
    group.add_function("price", price, description=price.__doc__)

    # Free batch preview tools (always registered - runnable in CI without funds).
    group.add_function("batch_validate", batch_validate, description=batch_validate.__doc__)
    group.add_function("batch_estimate", batch_estimate, description=batch_estimate.__doc__)

    # Paid tools (registered only when EVM_PRIVATE_KEY is set).
    group.add_function("balance", balance, description=balance.__doc__, filter_fn=_requires_evm_key)
    group.add_function("batch_send", batch_send, description=batch_send.__doc__, filter_fn=_requires_evm_key)
    group.add_function("escrow_create", escrow_create, description=escrow_create.__doc__, filter_fn=_requires_evm_key)
    group.add_function("rtp_discover", rtp_discover, description=rtp_discover.__doc__, filter_fn=_requires_evm_key)

    yield group
