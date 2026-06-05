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
"""Spraay x402 Gateway HTTP client.

Provides async HTTP methods for interacting with the Spraay x402 protocol
gateway, which enables AI agents to execute cryptocurrency payments across
15 blockchains using USDC micropayments.
"""

import json
import logging

import httpx

logger = logging.getLogger(__name__)


class SpraayClient:
    """Async HTTP client for the Spraay x402 gateway."""

    def __init__(self, gateway_url: str, timeout: int = 30):
        self.gateway_url = gateway_url.rstrip("/")
        self.timeout = timeout

    async def get(self, path: str, params: dict | None = None) -> str:
        """Make a GET request to the Spraay gateway.

        Args:
            path: API endpoint path (e.g., '/health', '/v1/chains').
            params: Optional query parameters.

        Returns:
            JSON string with the gateway response.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.gateway_url}{path}",
                    params=params,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
        except httpx.HTTPStatusError as e:
            logger.error("Spraay gateway HTTP error: %s %s", e.response.status_code, path)
            return json.dumps({"error": f"HTTP {e.response.status_code}", "path": path})
        except Exception as e:
            logger.error("Spraay gateway request failed: %s", e)
            return json.dumps({"error": str(e)})

    async def post(self, path: str, data: dict) -> str:
        """Make a POST request to the Spraay gateway.

        Args:
            path: API endpoint path (e.g., '/v1/batch-send').
            data: JSON body to send.

        Returns:
            JSON string with the gateway response.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.gateway_url}{path}",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
        except httpx.HTTPStatusError as e:
            logger.error("Spraay gateway HTTP error: %s %s", e.response.status_code, path)
            return json.dumps({"error": f"HTTP {e.response.status_code}", "path": path})
        except Exception as e:
            logger.error("Spraay gateway request failed: %s", e)
            return json.dumps({"error": str(e)})
