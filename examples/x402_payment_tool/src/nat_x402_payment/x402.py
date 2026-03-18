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

"""x402 protocol helpers for parsing 402 responses and constructing payment proofs.

The x402 protocol (https://github.com/coinbase/x402) uses HTTP 402 responses
to communicate payment requirements. The server includes payment details in
the response headers, and the client attaches a signed payment proof to the
retry request.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PaymentRequirement:
    """Parsed payment requirement from a 402 response.

    Attributes:
        amount: Payment amount in the token's smallest unit (e.g., USDC has 6 decimals).
        amount_usd: Payment amount in USD (derived from amount and token).
        recipient: Address to pay.
        token: Token contract address (e.g., USDC on Base).
        network: Chain identifier (e.g., "base").
        description: Human-readable description of what is being purchased.
        nonce: Unique nonce to prevent replay attacks.
        expires_at: Unix timestamp after which the payment requirement expires.
    """

    amount: int
    amount_usd: float
    recipient: str
    token: str
    network: str
    description: str
    nonce: str
    expires_at: int


def parse_402_response(headers: dict[str, str], body: bytes | str) -> PaymentRequirement | None:
    """Extract payment requirements from an HTTP 402 response.

    The x402 protocol encodes payment requirements in the response body as JSON.
    See: https://github.com/coinbase/x402/blob/main/README.md

    Args:
        headers: Response headers.
        body: Response body (JSON).

    Returns:
        PaymentRequirement if valid x402 response, None otherwise.
    """
    try:
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        data = json.loads(body)

        # x402 response format
        payment_info = data.get("payment", data)
        amount = int(payment_info.get("amount", 0))

        # USDC has 6 decimals
        token = payment_info.get("token", "")
        amount_usd = amount / 1_000_000 if "usdc" in token.lower() or amount > 0 else 0

        return PaymentRequirement(
            amount=amount,
            amount_usd=amount_usd,
            recipient=payment_info.get("recipient", ""),
            token=token,
            network=payment_info.get("network", "base"),
            description=payment_info.get("description", "Paid API access"),
            nonce=payment_info.get("nonce", ""),
            expires_at=int(payment_info.get("expires_at", time.time() + 300)),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Failed to parse 402 response as x402: %s", exc)
        return None


def sign_payment(
    requirement: PaymentRequirement,
    private_key: str,
) -> str:
    """Sign a payment proof for the given requirement.

    SECURITY NOTE: This function is the ONLY place the private key is used.
    It runs outside the agent's context window. The returned payment proof
    is a signed authorization that can only be used for this specific payment.

    Args:
        requirement: The payment requirement to fulfill.
        private_key: Hex-encoded private key for signing.

    Returns:
        Hex-encoded signed payment proof.
    """
    from eth_account import Account
    from eth_account.messages import encode_defunct

    # Construct the payment message
    message = json.dumps(
        {
            "amount": str(requirement.amount),
            "recipient": requirement.recipient,
            "token": requirement.token,
            "nonce": requirement.nonce,
            "network": requirement.network,
            "expires_at": requirement.expires_at,
        },
        separators=(",", ":"),
        sort_keys=True,
    )

    # Sign with the agent's wallet key
    signable = encode_defunct(text=message)
    signed = Account.sign_message(signable, private_key=private_key)

    logger.info(
        "Payment signed: $%.4f to %s (nonce: %s)",
        requirement.amount_usd,
        requirement.recipient[:10] + "...",
        requirement.nonce[:8] + "...",
    )

    return signed.signature.hex()
