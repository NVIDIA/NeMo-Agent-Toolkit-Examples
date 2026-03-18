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

"""Spending policy enforcement for agent payments.

The spending policy is evaluated BEFORE any payment is signed.
This ensures the agent cannot exceed configured limits even if
the LLM generates instructions to do so.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SpendingPolicy:
    """Configurable spending limits for agent payments.

    Attributes:
        max_per_transaction_usd: Maximum amount for a single payment.
        max_daily_usd: Maximum total spend in a rolling 24-hour window.
        allowed_recipients: Set of addresses the agent is allowed to pay.
            If empty, all recipients are allowed.
        require_confirmation: If True, the tool returns a confirmation
            request instead of paying automatically.
    """

    max_per_transaction_usd: float = 1.00
    max_daily_usd: float = 10.00
    allowed_recipients: set[str] = field(default_factory=set)
    require_confirmation: bool = False

    # Internal tracking
    _daily_spend: float = field(default=0.0, repr=False)
    _daily_reset_time: float = field(default=0.0, repr=False)
    _transaction_log: list[dict] = field(default_factory=list, repr=False)

    def check(self, amount_usd: float, recipient: str) -> tuple[bool, str]:
        """Evaluate whether a payment is allowed under the current policy.

        Args:
            amount_usd: Payment amount in USD.
            recipient: Recipient address.

        Returns:
            Tuple of (allowed: bool, reason: str).
        """
        # Reset daily counter if 24h have passed
        now = time.time()
        if now - self._daily_reset_time > 86400:
            self._daily_spend = 0.0
            self._daily_reset_time = now

        # Check per-transaction limit
        if amount_usd > self.max_per_transaction_usd:
            reason = (
                f"Amount ${amount_usd:.2f} exceeds per-transaction limit "
                f"of ${self.max_per_transaction_usd:.2f}"
            )
            logger.warning("Payment DENIED: %s", reason)
            return False, reason

        # Check daily limit
        if self._daily_spend + amount_usd > self.max_daily_usd:
            reason = (
                f"Amount ${amount_usd:.2f} would exceed daily limit "
                f"of ${self.max_daily_usd:.2f} "
                f"(spent today: ${self._daily_spend:.2f})"
            )
            logger.warning("Payment DENIED: %s", reason)
            return False, reason

        # Check recipient allowlist
        if self.allowed_recipients and recipient not in self.allowed_recipients:
            reason = f"Recipient {recipient} is not in the allowed list"
            logger.warning("Payment DENIED: %s", reason)
            return False, reason

        return True, "Payment approved"

    def record_payment(self, amount_usd: float, recipient: str, tx_hash: str) -> None:
        """Record a completed payment for audit and daily tracking."""
        self._daily_spend += amount_usd
        self._transaction_log.append(
            {
                "amount_usd": amount_usd,
                "recipient": recipient,
                "tx_hash": tx_hash,
                "timestamp": time.time(),
            }
        )
        logger.info(
            "Payment recorded: $%.2f to %s (tx: %s) — daily total: $%.2f / $%.2f",
            amount_usd,
            recipient,
            tx_hash,
            self._daily_spend,
            self.max_daily_usd,
        )
