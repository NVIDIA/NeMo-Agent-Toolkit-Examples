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

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function import FunctionGroup
from nat.cli.register_workflow import register_function_group
from nat.data_models.function import FunctionGroupBaseConfig

from .spraay_client import SpraayClient

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
            JSON string with the list of gateway routes.
        """
        return await client.get("/v1/routes")

    async def chains(query: str = "") -> str:
        """List all supported blockchains on the Spraay gateway.

        This is a free query - no x402 USDC payment is required.

        Args:
            query: Unused; the endpoint is fixed. Provided for agent compatibility.

        Returns:
            JSON string with the list of supported chains.
        """
        return await client.get("/v1/chains")

    async def balance(query: str) -> str:
        """Check the token balance of a wallet address on a specific blockchain.

        This is a free query - no x402 USDC payment is required.

        Args:
            query: A string containing the wallet address and optionally
                the chain and token, e.g.:
                '0xAd62...c8 on base for USDC'
                '0xAd62...c8' (defaults to Base/USDC)

        Returns:
            JSON string with the wallet balance.
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
            "/v1/balance",
            params={"address": address, "chain": chain, "token": token},
        )

    async def price(query: str) -> str:
        """Get the current price of a token on a specific blockchain.

        This is a free query - no x402 USDC payment is required.

        Args:
            query: A string containing the token symbol and optionally
                the chain, e.g.:
                'ETH on base'
                'USDC' (defaults to Base)

        Returns:
            JSON string with the current token price.
        """
        parts = query.strip().split()
        token = parts[0].upper() if parts else "ETH"
        chain = "base"

        lower_parts = [p.lower() for p in parts]
        if "on" in lower_parts:
            idx = lower_parts.index("on")
            if idx + 1 < len(parts):
                chain = parts[idx + 1].lower()

        return await client.get(
            "/v1/price",
            params={"token": token, "chain": chain},
        )

    group.add_function("health", health, description=health.__doc__)
    group.add_function("routes", routes, description=routes.__doc__)
    group.add_function("chains", chains, description=chains.__doc__)
    group.add_function("balance", balance, description=balance.__doc__)
    group.add_function("price", price, description=price.__doc__)

    yield group
