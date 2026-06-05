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

Registers Spraay gateway tools using the @register_function decorator
so they can be referenced by _type in workflow config.yml files.

Each tool is a separate registered function with its own config class,
following the NAT plugin pattern.
"""

import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from .spraay_client import SpraayClient

logger = logging.getLogger(__name__)


# Configuration classes
# Each _type in config.yml maps to a FunctionBaseConfig subclass via its name=.


class SpraayGatewayToolConfig(FunctionBaseConfig, name="spraay_gateway_tool"):
    """Generic Spraay gateway GET endpoint tool."""

    gateway_url: str = Field(
        default="https://gateway.spraay.app",
        description="Base URL of the Spraay x402 gateway",
    )
    endpoint: str = Field(
        description="API endpoint path (e.g., /health, /v1/routes, /v1/chains)",
    )
    method: str = Field(
        default="GET",
        description="HTTP method (GET or POST)",
    )


class SpraayBalanceToolConfig(FunctionBaseConfig, name="spraay_balance_tool"):
    """Tool to check wallet token balances via the Spraay gateway."""

    gateway_url: str = Field(
        default="https://gateway.spraay.app",
        description="Base URL of the Spraay x402 gateway",
    )


class SpraayPriceToolConfig(FunctionBaseConfig, name="spraay_price_tool"):
    """Tool to get token prices via the Spraay gateway."""

    gateway_url: str = Field(
        default="https://gateway.spraay.app",
        description="Base URL of the Spraay x402 gateway",
    )


# Tool registrations


@register_function(config_type=SpraayGatewayToolConfig)
async def spraay_gateway_tool(config: SpraayGatewayToolConfig, builder: Builder):
    """Register a generic Spraay gateway query tool."""

    client = SpraayClient(gateway_url=config.gateway_url)
    endpoint = config.endpoint

    async def _query(query: str) -> str:
        """Query the Spraay x402 gateway.

        Fetches data from the configured Spraay gateway endpoint.
        This is a free query - no x402 USDC payment is required.

        Args:
            query: A natural language description of what to look up
                (the endpoint is pre-configured, so this is for context).

        Returns:
            JSON string with the gateway response data.
        """
        return await client.get(endpoint)

    yield FunctionInfo.from_fn(
        _query,
        description=config.description or f"Query Spraay gateway endpoint: {endpoint}",
    )


@register_function(config_type=SpraayBalanceToolConfig)
async def spraay_balance_tool(config: SpraayBalanceToolConfig, builder: Builder):
    """Register the Spraay balance lookup tool."""

    client = SpraayClient(gateway_url=config.gateway_url)

    async def _check_balance(query: str) -> str:
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
        # Parse the query to extract address, chain, and token
        parts = query.strip().split()
        address = parts[0] if parts else query.strip()
        chain = "base"
        token = "USDC"

        # Simple parsing: look for 'on <chain>' and 'for <token>'
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

    yield FunctionInfo.from_fn(
        _check_balance,
        description=config.description or "Check token balance of a wallet address on a specific chain",
    )


@register_function(config_type=SpraayPriceToolConfig)
async def spraay_price_tool(config: SpraayPriceToolConfig, builder: Builder):
    """Register the Spraay token price lookup tool."""

    client = SpraayClient(gateway_url=config.gateway_url)

    async def _get_price(query: str) -> str:
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

    yield FunctionInfo.from_fn(
        _get_price,
        description=config.description or "Get the current price of a token on a specific chain",
    )
