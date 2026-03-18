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

"""
Wallet signing abstraction for x402 payments.

Supports two modes:
1. Inline signing (development) — private key in env var
2. Remote signer (production) — signing key in a separate process

The agent process NEVER has direct access to the private key in production.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WalletSigner(ABC):
    """Abstract base class for wallet signing operations."""

    @abstractmethod
    def sign_payment(
        self,
        amount: int,
        recipient: str,
        asset: str,
        network: str,
    ) -> dict[str, Any]:
        """
        Sign an x402 payment.

        Args:
            amount: Payment amount in smallest unit (e.g., USDC uses 6 decimals)
            recipient: Payment recipient address
            asset: Token contract address
            network: Target network (e.g., "base")

        Returns:
            Dict with "header" (x402 payment header), "tx_hash", and optionally "token"
        """
        ...

    @abstractmethod
    def get_address(self) -> str:
        """Return the wallet's public address."""
        ...

    @abstractmethod
    def get_balance(self, asset: str = "", network: str = "base") -> float:
        """Return the wallet's balance for the given asset."""
        ...


class InlineWalletSigner(WalletSigner):
    """
    Development-only signer that uses a private key from an environment variable.

    WARNING: This mode stores the private key in the same process as the agent.
    Use RemoteWalletSigner for production deployments.
    """

    def __init__(self, private_key: str | None = None):
        self._private_key = private_key or os.getenv("WALLET_PRIVATE_KEY", "")
        if not self._private_key:
            raise ValueError(
                "WALLET_PRIVATE_KEY not set. For production, use WALLET_SIGNER_URL instead."
            )

        try:
            from eth_account import Account

            self._account = Account.from_key(self._private_key)
            logger.info("Inline wallet initialized: %s", self._account.address)
        except ImportError:
            raise ImportError("eth-account is required for inline signing: pip install eth-account")

    def get_address(self) -> str:
        return self._account.address

    def get_balance(self, asset: str = "", network: str = "base") -> float:
        # Simplified — in production, query the chain
        logger.warning("Balance check not implemented for inline signer; returning 0")
        return 0.0

    def sign_payment(
        self,
        amount: int,
        recipient: str,
        asset: str,
        network: str,
    ) -> dict[str, Any]:
        """Sign an x402 payment using the local private key."""
        from eth_account.messages import encode_defunct

        # Construct the x402 payment message
        message_data = {
            "scheme": "exact",
            "network": network,
            "amount": str(amount),
            "asset": asset,
            "payTo": recipient,
            "payer": self._account.address,
        }

        # Sign the message
        message = encode_defunct(text=json.dumps(message_data, sort_keys=True))
        signed = self._account.sign_message(message)

        return {
            "header": json.dumps(
                {
                    **message_data,
                    "signature": signed.signature.hex(),
                }
            ),
            "tx_hash": signed.signature.hex()[:16],  # Shortened for logging
            "token": "",
        }


class RemoteWalletSigner(WalletSigner):
    """
    Production signer that delegates to a separate signing process.

    The signing key never enters the agent's process memory.
    The signer process runs on a separate port and only accepts
    pre-validated payment requests.
    """

    def __init__(self, signer_url: str | None = None):
        self._signer_url = signer_url or os.getenv("WALLET_SIGNER_URL", "")
        if not self._signer_url:
            raise ValueError("WALLET_SIGNER_URL not set")
        logger.info("Remote wallet signer: %s", self._signer_url)

    def get_address(self) -> str:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{self._signer_url}/address")
            resp.raise_for_status()
            return resp.json()["address"]

    def get_balance(self, asset: str = "", network: str = "base") -> float:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{self._signer_url}/balance",
                params={"asset": asset, "network": network},
            )
            resp.raise_for_status()
            return resp.json()["balance"]

    def sign_payment(
        self,
        amount: int,
        recipient: str,
        asset: str,
        network: str,
    ) -> dict[str, Any]:
        """Request the remote signer to sign an x402 payment."""
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self._signer_url}/sign",
                json={
                    "amount": str(amount),
                    "recipient": recipient,
                    "asset": asset,
                    "network": network,
                },
            )
            resp.raise_for_status()
            return resp.json()


def create_wallet_signer() -> WalletSigner:
    """
    Factory function that creates the appropriate signer based on environment.

    Priority:
    1. WALLET_SIGNER_URL → RemoteWalletSigner (production)
    2. WALLET_PRIVATE_KEY → InlineWalletSigner (development)
    """
    signer_url = os.getenv("WALLET_SIGNER_URL", "")
    if signer_url:
        return RemoteWalletSigner(signer_url)

    private_key = os.getenv("WALLET_PRIVATE_KEY", "")
    if private_key:
        return InlineWalletSigner(private_key)

    raise ValueError(
        "No wallet signer configured. Set WALLET_SIGNER_URL (production) "
        "or WALLET_PRIVATE_KEY (development)."
    )
