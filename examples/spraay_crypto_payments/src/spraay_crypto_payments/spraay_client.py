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

Two modes:

* **Dry-run mode** (no ``EVM_PRIVATE_KEY``): paid endpoints return a structured
  payment quote parsed from the gateway's HTTP 402 response. No wallet, no
  signing, no funds move. Safe for CI and demos.
* **Live mode** (``EVM_PRIVATE_KEY`` set): paid requests are routed through the
  x402 SDK's payment transport. When the gateway responds ``402 Payment
  Required`` (x402Version 2), the SDK signs an EIP-3009 ``TransferWithAuthorization``
  for USDC on Base (the ``exact`` scheme), attaches it as the ``X-PAYMENT``
  header, and retries. The gateway's facilitator settles the USDC transfer
  on-chain and returns the real API result plus an ``X-PAYMENT-RESPONSE``
  header containing the settlement transaction hash.

The private key is read once from the environment, used only to construct the
in-memory signer, and is never logged, echoed, or included in any return value.
"""

import base64
import json
import logging
import os
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

# Base-unit decimals for the tokens the Spraay gateway documents at
# GET /api/v1/tokens. The paid /api/v1/batch/execute endpoint requires each
# amount in raw base units (e.g. 1.5 USDC -> "1500000"), unlike the free
# validate/estimate endpoints which accept human-decimal amounts.
_TOKEN_DECIMALS = {
    "ETH": 18,
    "WETH": 18,
    "USDC": 6,
    "USDT": 6,
    "EURC": 6,
    "DAI": 18,
}
# Standard ERC-20 default for any token not in the map above.
_DEFAULT_TOKEN_DECIMALS = 18


def to_batch_execute_payload(data: dict) -> dict:
    """Convert a BPA batch into the shape /api/v1/batch/execute requires.

    The free ``/free/validate-batch`` and ``/free/estimate-batch`` endpoints
    accept recipients as ``[{"to": addr, "amount": "1.5"}, ...]`` with
    human-decimal amounts. The paid ``/api/v1/batch/execute`` endpoint (per the
    402 response's ``extensions.bazaar`` schema) instead requires two parallel
    arrays — a flat ``recipients`` address list and an ``amounts`` list in raw
    base units — plus ``token`` and ``sender``.

    This converts the former into the latter. If ``recipients`` is already a
    flat list of address strings (already converted), the payload is returned
    unchanged.

    Args:
        data: Batch dict with ``recipients`` (list of ``{"to", "amount"}``),
            ``token``, ``sender``, and optionally ``chain``.

    Returns:
        A new dict with ``recipients`` (addresses) and ``amounts`` (raw
        base-unit strings) arrays, preserving ``token``, ``sender`` and any
        other top-level keys.

    Raises:
        ValueError: if a recipient is missing an address or amount, or an
            amount is not a valid number.
    """
    recipients = data.get("recipients", [])

    # Already in the flat-array form (or empty) — nothing to convert.
    if not recipients or not isinstance(recipients[0], dict):
        return dict(data)

    token = str(data.get("token", "USDC")).upper()
    decimals = _TOKEN_DECIMALS.get(token, _DEFAULT_TOKEN_DECIMALS)
    scale = Decimal(10) ** decimals

    addresses: list[str] = []
    amounts: list[str] = []
    for rec in recipients:
        addr = rec.get("to")
        amount = rec.get("amount")
        if not addr:
            raise ValueError("Batch recipient is missing a 'to' address.")
        if amount is None or amount == "":
            raise ValueError(f"Batch recipient {addr} is missing an amount.")
        try:
            raw = int((Decimal(str(amount)) * scale).to_integral_value())
        except Exception as e:
            raise ValueError(f"Invalid amount {amount!r} for recipient {addr}: {e}") from e
        addresses.append(addr)
        amounts.append(str(raw))

    payload = dict(data)
    payload["recipients"] = addresses
    payload["amounts"] = amounts
    return payload


class SpraayClient:
    """Async HTTP client for the Spraay x402 gateway with x402 payment support."""

    def __init__(self, gateway_url: str, timeout: int = 30):
        self.gateway_url = gateway_url.rstrip("/")
        self.timeout = timeout
        # Optional private key for x402 payment execution (never logged/echoed).
        self.private_key = os.environ.get("EVM_PRIVATE_KEY")
        # Lazily-built x402 client + signer, cached across requests. Only ever
        # constructed in live mode; the dry-run path never imports x402.
        self._x402_client = None
        self._payer_address: str | None = None

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

    def _get_x402_client(self):
        """Lazily build and cache the x402 payment client from EVM_PRIVATE_KEY.

        Constructs an eth-account signer and registers the EVM ``exact`` payment
        scheme (V2 ``eip155:*`` wildcard + legacy V1 networks). The resulting
        x402 client is reused for every live request.

        Returns:
            An ``x402Client`` configured to sign USDC payments.

        Raises:
            RuntimeError: if the x402/eth-account dependencies are missing or the
                private key is invalid. The error message never contains the key.
        """
        if self._x402_client is not None:
            return self._x402_client

        try:
            from eth_account import Account
            from x402 import x402Client
            from x402.mechanisms.evm.exact import register_exact_evm_client
            from x402.mechanisms.evm.signers import EthAccountSigner
        except ImportError as e:
            raise RuntimeError(
                "Live mode requires the x402 SDK with EVM + httpx extras. "
                "Install with: uv pip install -e . (pulls x402[evm,httpx])."
            ) from e

        key = self.private_key or ""
        if not key.startswith("0x"):
            key = "0x" + key
        try:
            account = Account.from_key(key)
        except Exception:
            # Do not chain or echo the original error — it could reference the
            # malformed key material.
            raise RuntimeError("EVM_PRIVATE_KEY is not a valid EVM private key.") from None

        client = x402Client()
        register_exact_evm_client(client, EthAccountSigner(account))
        self._x402_client = client
        self._payer_address = account.address
        return client

    @staticmethod
    def _safe_json(response: "httpx.Response"):
        """Return the response body as parsed JSON, or raw text if not JSON."""
        try:
            return response.json()
        except Exception:
            return response.text

    @staticmethod
    def _decode_payment_response(response: "httpx.Response"):
        """Decode the base64 X-PAYMENT-RESPONSE settlement header, if present.

        The gateway returns settlement details (success flag, transaction hash,
        network, payer) in this header after a successful x402 payment.
        """
        raw = response.headers.get("x-payment-response") or response.headers.get("payment-response")
        if not raw:
            return None
        try:
            return json.loads(base64.b64decode(raw))
        except Exception:
            return raw

    async def _live_request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> str:
        """Execute a paid request in live mode via the x402 payment transport.

        Routes the request through an httpx client wrapped with the x402 SDK's
        payment transport. A 402 from the gateway is handled automatically: the
        SDK signs a USDC EIP-3009 authorization, retries with the X-PAYMENT
        header, and the gateway settles on-chain. This moves real funds.

        Args:
            method: "GET" or "POST".
            path: Gateway endpoint path.
            params: Query parameters (GET).
            json_data: JSON body (POST).

        Returns:
            JSON string with the settled API result and settlement details, or a
            structured error. The private key is never included.
        """
        try:
            x402_client = self._get_x402_client()
            from x402.http.clients.httpx import PaymentError, wrapHttpxWithPayment
        except RuntimeError as e:
            return json.dumps({"mode": "live", "error": str(e), "path": path}, indent=2)
        except ImportError as e:
            return json.dumps({
                "mode": "live",
                "error": f"Live mode dependencies missing: {e}",
                "path": path,
            }, indent=2)

        url = f"{self.gateway_url}{path}"
        headers = {"Content-Type": "application/json"}
        try:
            async with wrapHttpxWithPayment(x402_client, timeout=self.timeout) as http:
                if method == "GET":
                    response = await http.get(url, params=params, headers=headers)
                else:
                    response = await http.post(url, json=json_data, headers=headers)

                if response.status_code == 402:
                    # The payment was signed and submitted but the gateway did
                    # not accept it. Most common cause: the paying wallet holds
                    # insufficient USDC, or the payment window expired.
                    return json.dumps({
                        "mode": "live",
                        "error": (
                            "Payment was signed and submitted but the gateway rejected it "
                            "(HTTP 402). Check that the paying wallet holds enough USDC on the "
                            "target chain to cover the payment plus the transfer amount."
                        ),
                        "gateway_response": self._safe_json(response),
                        "path": path,
                    }, indent=2)

                response.raise_for_status()
                settlement = self._decode_payment_response(response)
                if settlement is None:
                    # No payment was required (e.g. a free endpoint hit in live
                    # mode) — return the raw body, identical to dry-run mode.
                    return json.dumps(self._safe_json(response), indent=2)
                # A payment settled: surface the result plus the settlement
                # details (transaction hash, payer, network).
                return json.dumps({
                    "mode": "live",
                    "result": self._safe_json(response),
                    "settlement": settlement,
                }, indent=2)
        except PaymentError as e:
            logger.error("x402 payment failed for %s", path)
            return json.dumps({
                "mode": "live",
                "error": f"x402 payment execution failed: {e}",
                "path": path,
            }, indent=2)
        except httpx.HTTPStatusError as e:
            logger.error("Spraay gateway HTTP error: %s %s", e.response.status_code, path)
            return json.dumps({
                "mode": "live",
                "error": f"HTTP {e.response.status_code}",
                "response_body": self._safe_json(e.response),
                "path": path,
            }, indent=2)
        except Exception as e:
            logger.error("Live x402 request failed for %s", path)
            return json.dumps({"mode": "live", "error": str(e), "path": path}, indent=2)

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
        # Live mode: route paid endpoints through the x402 payment transport,
        # which signs and settles automatically. (Free endpoints never hit 402,
        # so they pass straight through.)
        if self.private_key:
            return await self._live_request("GET", path, params=params)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.gateway_url}{path}",
                    params=params,
                    headers={"Content-Type": "application/json"},
                )

                # Handle 402 Payment Required (dry-run: return structured quote)
                if response.status_code == 402:
                    body = response.json()
                    dry_run_result = self._parse_402_response(path, body)
                    return json.dumps(dry_run_result, indent=2)

                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 402:  # 402 already handled above
                logger.error("Spraay gateway HTTP error: %s %s", e.response.status_code, path)
                return json.dumps({
                    "error": f"HTTP {e.response.status_code}",
                    "response_body": self._safe_json(e.response),
                    "path": path,
                })
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
        # Live mode: route paid endpoints through the x402 payment transport,
        # which signs and settles automatically. In live mode a POST to a paid
        # endpoint such as /api/v1/batch/execute moves real funds.
        if self.private_key:
            return await self._live_request("POST", path, json_data=data)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.gateway_url}{path}",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )

                # Handle 402 Payment Required (dry-run: return structured quote)
                if response.status_code == 402:
                    body = response.json()
                    dry_run_result = self._parse_402_response(path, body)
                    return json.dumps(dry_run_result, indent=2)

                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 402:  # 402 already handled above
                logger.error("Spraay gateway HTTP error: %s %s", e.response.status_code, path)
                return json.dumps({
                    "error": f"HTTP {e.response.status_code}",
                    "response_body": self._safe_json(e.response),
                    "path": path,
                })
            raise  # Re-raise if we missed a 402
        except Exception as e:
            logger.error("Spraay gateway request failed: %s", e)
            return json.dumps({"error": str(e)})
