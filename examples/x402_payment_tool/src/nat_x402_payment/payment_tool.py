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

"""Payment-enabled API tool for NeMo Agent Toolkit.

This tool wraps HTTP requests to paid APIs that use the x402 protocol.
When a 402 response is received, it evaluates the spending policy,
signs a payment proof, and retries the request.

Usage in a NeMo Agent Toolkit config:

    tools:
      - name: paid_api
        type: nat_x402_payment.PaidAPITool
        config:
          spending_policy:
            max_per_transaction_usd: 1.00
            max_daily_usd: 10.00
"""

from __future__ import annotations

import logging
import os

import httpx
from langchain_core.tools import tool

from nat_x402_payment.spending_policy import SpendingPolicy
from nat_x402_payment.x402 import PaymentRequirement, parse_402_response, sign_payment

logger = logging.getLogger(__name__)

# Module-level spending policy (configured at startup)
_spending_policy = SpendingPolicy()
_wallet_key: str | None = None
_mock_mode: bool = False


def configure(
    max_per_transaction_usd: float = 1.00,
    max_daily_usd: float = 10.00,
    allowed_recipients: list[str] | None = None,
    require_confirmation: bool = False,
    mock: bool = False,
) -> None:
    """Configure the payment tool's spending policy and wallet.

    Call this at startup before the agent loop begins.
    """
    global _spending_policy, _wallet_key, _mock_mode

    _spending_policy = SpendingPolicy(
        max_per_transaction_usd=max_per_transaction_usd,
        max_daily_usd=max_daily_usd,
        allowed_recipients=set(allowed_recipients or []),
        require_confirmation=require_confirmation,
    )

    _wallet_key = os.environ.get("AGENT_WALLET_PRIVATE_KEY")
    _mock_mode = mock

    if not _wallet_key and not mock:
        logger.warning(
            "AGENT_WALLET_PRIVATE_KEY not set. Payment tool will fail on real 402 responses. "
            "Set mock=True for testing without a wallet."
        )

    logger.info(
        "Payment tool configured: max_tx=$%.2f, max_daily=$%.2f, mock=%s",
        max_per_transaction_usd,
        max_daily_usd,
        mock,
    )


@tool
def paid_api_request(url: str, method: str = "GET") -> str:
    """Make an HTTP request to a paid API, automatically handling x402 payment flows.

    If the API returns HTTP 402, this tool evaluates the cost against the
    spending policy, signs a payment proof, and retries the request.

    Args:
        url: The API endpoint URL to call.
        method: HTTP method (GET, POST). Defaults to GET.

    Returns:
        The API response content, prefixed with payment status if a payment was made.
    """
    headers = {"User-Agent": "NeMo-Agent-Toolkit/1.0"}

    with httpx.Client(timeout=30.0) as client:
        # Initial request
        response = client.request(method, url, headers=headers)

        # If not 402, return directly
        if response.status_code != 402:
            return f"[HTTP {response.status_code}] {response.text}"

        # Parse x402 payment requirement
        requirement = parse_402_response(
            dict(response.headers), response.content
        )

        if requirement is None:
            return (
                "[PAYMENT ERROR] Received 402 but could not parse x402 payment "
                "requirements from the response. The API may not support x402."
            )

        # Check spending policy BEFORE signing
        allowed, reason = _spending_policy.check(
            requirement.amount_usd, requirement.recipient
        )

        if not allowed:
            return (
                f"[PAYMENT DENIED] {reason}. "
                f"The API requires ${requirement.amount_usd:.4f} "
                f"for: {requirement.description}"
            )

        if _spending_policy.require_confirmation:
            return (
                f"[PAYMENT CONFIRMATION REQUIRED] The API requests "
                f"${requirement.amount_usd:.4f} for: {requirement.description}. "
                f"Recipient: {requirement.recipient}. "
                f"Please confirm to proceed."
            )

        # Sign the payment
        if _mock_mode:
            payment_proof = "mock_payment_proof_for_testing"
            tx_hash = "0x" + "mock" * 16
        else:
            if not _wallet_key:
                return "[PAYMENT ERROR] No wallet key configured. Cannot sign payment."

            payment_proof = sign_payment(requirement, _wallet_key)
            tx_hash = "0x" + payment_proof[:64]  # Simplified; real impl tracks on-chain

        # Retry with payment proof
        headers["X-Payment"] = payment_proof
        headers["X-Payment-Token"] = requirement.token
        headers["X-Payment-Network"] = requirement.network

        response = client.request(method, url, headers=headers)

        # Record the payment
        _spending_policy.record_payment(
            requirement.amount_usd, requirement.recipient, tx_hash
        )

        return (
            f"[PAID ${requirement.amount_usd:.4f} — {requirement.description}] "
            f"{response.text}"
        )


# Export for NeMo Agent Toolkit tool registration
PaidAPITool = paid_api_request
