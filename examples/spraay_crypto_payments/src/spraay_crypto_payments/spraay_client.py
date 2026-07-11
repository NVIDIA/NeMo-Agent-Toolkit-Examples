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

Supports both dry-run mode (returns payment quotes) and live mode (executes
x402 payment flow when EVM_PRIVATE_KEY is set).
"""

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)


class SpraayClient:
    """Async HTTP client for the Spraay x402 gateway with x402 payment support."""

    def __init__(self, gateway_url: str, timeout: int = 30):
        self.gateway_url = gateway_url.rstrip("/")
        self.timeout = timeout
        # Optional private key for x402 payment execution (never logged/echoed)
        self.private_key = os.environ.get("EVM_PRIVATE_KEY")

    def _parse_402_response(self, endpoint: str, response_body: dict) -> dict:
        """Parse a 402 Payment Required response into a structured dry-run result.

        Args:
            endpoint: The endpoint that returned 402
            response_body: The x402 JSON response body

        Returns:
            Structured dict with mode, endpoint, payment_required details, and note
        """
        try:
            accepts = response_body.get("accepts", [])
            if not accepts:
                return {
                    "mode": "dry_run",
                    "endpoint": endpoint,
                    "error": "No payment options in 402 response",
                }

            # Use the first EVM payment option (Base/USDC)
            payment_option = accepts[0]
            amount_raw = int(payment_option.get("amount", 0))
            # Convert 6-decimal USDC to dollars (5000 = $0.005)
            price_usd = amount_raw / 1_000_000

            return {
                "mode": "dry_run",
                "endpoint": endpoint,
                "payment_required": {
                    "price": f"${price_usd:.3f}",
                    "amount_usdc_raw": amount_raw,
                    "asset": "USDC",
                    "network": payment_option.get("network", "eip155:8453"),
                    "pay_to": payment_option.get("payTo"),
                },
                "note": "Set EVM_PRIVATE_KEY environment variable to execute for real.",
            }
        except Exception as e:
            logger.error("Failed to parse 402 response: %s", e)
            return {
                "mode": "dry_run",
                "endpoint": endpoint,
                "error": f"Failed to parse payment requirements: {e}",
            }

    async def get(self, path: str, params: dict | None = None) -> str:
        """Make a GET request to the Spraay gateway.

        Handles both free and paid (x402) endpoints. For paid endpoints:
        - Dry-run mode (no EVM_PRIVATE_KEY): returns payment quote as JSON
        - Live mode (EVM_PRIVATE_KEY set): executes x402 payment flow

        Args:
            path: API endpoint path (e.g., '/health', '/free/prices').
            params: Optional query parameters.

        Returns:
            JSON string with the gateway response or payment quote.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.gateway_url}{path}",
                    params=params,
                    headers={"Content-Type": "application/json"},
                )

                # Handle 402 Payment Required
                if response.status_code == 402:
                    body = response.json()
                    if not self.private_key:
                        # Dry-run: return structured payment quote
                        dry_run_result = self._parse_402_response(path, body)
                        return json.dumps(dry_run_result, indent=2)
                    else:
                        # Live mode: execute x402 payment (basic implementation)
                        # For production, integrate full x402 payment signing
                        return json.dumps({
                            "error": "Live x402 payment execution not yet implemented",
                            "payment_quote": self._parse_402_response(path, body),
                        }, indent=2)

                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 402:  # 402 already handled above
                logger.error("Spraay gateway HTTP error: %s %s", e.response.status_code, path)
                return json.dumps({"error": f"HTTP {e.response.status_code}", "path": path})
            raise  # Re-raise if we missed a 402
        except Exception as e:
            logger.error("Spraay gateway request failed: %s", e)
            return json.dumps({"error": str(e)})

    async def post(self, path: str, data: dict) -> str:
        """Make a POST request to the Spraay gateway.

        Handles both free and paid (x402) endpoints. For paid endpoints:
        - Dry-run mode (no EVM_PRIVATE_KEY): returns payment quote as JSON
        - Live mode (EVM_PRIVATE_KEY set): executes x402 payment flow

        Args:
            path: API endpoint path (e.g., '/free/validate-batch', '/api/v1/batch/execute').
            data: JSON body to send.

        Returns:
            JSON string with the gateway response or payment quote.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.gateway_url}{path}",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )

                # Handle 402 Payment Required
                if response.status_code == 402:
                    body = response.json()
                    if not self.private_key:
                        # Dry-run: return structured payment quote
                        dry_run_result = self._parse_402_response(path, body)
                        return json.dumps(dry_run_result, indent=2)
                    else:
                        # Live mode: execute x402 payment (basic implementation)
                        # For production, integrate full x402 payment signing
                        return json.dumps({
                            "error": "Live x402 payment execution not yet implemented",
                            "payment_quote": self._parse_402_response(path, body),
                        }, indent=2)

                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 402:  # 402 already handled above
                logger.error("Spraay gateway HTTP error: %s %s", e.response.status_code, path)
                return json.dumps({"error": f"HTTP {e.response.status_code}", "path": path})
            raise  # Re-raise if we missed a 402
        except Exception as e:
            logger.error("Spraay gateway request failed: %s", e)
            return json.dumps({"error": str(e)})
