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
x402 Payment Tool — NAT Functions for HTTP 402 Payment Negotiation

Registers a payment-enabled fetch tool with NeMo Agent Toolkit that:
1. Requests data from a URL
2. Detects HTTP 402 (Payment Required) responses
3. Parses x402 payment requirements
4. Checks against a configurable spending policy
5. Signs payment via an isolated wallet signer
6. Retries with payment proof attached

Security architecture:
- Spending policy enforced BEFORE signing (not after)
- Wallet key isolated from agent process (remote signer for production)
- Recipient allowlisting prevents payments to arbitrary addresses
- Full audit trail for all payment attempts
"""

import json
import logging
from datetime import datetime
from datetime import timezone

import httpx
from pydantic import BaseModel
from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.builder import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig
from nat_x402_payment.wallet import create_wallet_signer

logger = logging.getLogger(__name__)


class FetchPaidApiConfig(FunctionBaseConfig, name="fetch_paid_api"):
    """Fetch data from a URL that may require x402 payment."""

    max_per_transaction: float = Field(
        default=0.10,
        description="Maximum USDC per single payment",
    )
    max_daily_spend: float = Field(
        default=5.00,
        description="Daily spending cap in USDC",
    )
    allowed_recipients: list[str] = Field(
        default_factory=list,
        description="Allowlisted payment recipient addresses (empty = allow all)",
    )
    wallet_signer_url: str = Field(
        default="",
        description="URL of the remote wallet signer process (leave empty for inline dev mode)",
    )
    request_timeout: float = Field(
        default=30.0,
        description="HTTP request timeout in seconds",
    )


class GetPaymentStatusConfig(FunctionBaseConfig, name="get_payment_status"):
    """Get the current spending status and payment history."""

    pass


# Module-level state for spending tracking across tool calls.
# Using a mutable container avoids `global` statements (PLW0603).
_spend_state: dict = {
    "daily_spent": 0.0,
    "last_reset_date": "",
}
_payment_log: list[dict] = []


def _check_spending_policy(
    amount: float,
    recipient: str,
    max_per_tx: float,
    max_daily: float,
    allowed_recipients: list[str],
) -> tuple[bool, str]:
    """Evaluate whether a payment is allowed under the current policy."""
    # spending state accessed via _spend_state dict

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if today != _spend_state["last_reset_date"]:
        _spend_state["daily_spent"] = 0.0
        _spend_state["last_reset_date"] = today

    if amount > max_per_tx:
        return False, f"Amount {amount:.4f} USDC exceeds per-transaction limit {max_per_tx:.4f} USDC"

    if _spend_state["daily_spent"] + amount > max_daily:
        remaining = max_daily - _spend_state["daily_spent"]
        spent = _spend_state["daily_spent"]
        return (
            False,
            f"Would exceed daily limit. Spent today: {spent:.4f},"
            f" remaining: {remaining:.4f} USDC",
        )

    if allowed_recipients and recipient not in allowed_recipients:
        return False, f"Recipient {recipient} not in allowlist"

    return True, "APPROVED"


def _parse_x402_requirements(response: httpx.Response) -> dict:
    """Parse x402 payment requirements from a 402 response."""
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        header = response.headers.get("x-payment-required", "")
        if header:
            data = json.loads(header)
        else:
            return {}

    if "accepts" not in data or not data["accepts"]:
        return {}

    accept = data["accepts"][0]
    decimals = 6  # USDC
    raw_amount = int(accept.get("maxAmountRequired", "0"))
    amount = raw_amount / (10**decimals)

    return {
        "amount": amount,
        "raw_amount": raw_amount,
        "recipient": accept.get("payTo", ""),
        "asset": accept.get("asset", ""),
        "network": accept.get("network", "base"),
        "resource": accept.get("resource", ""),
        "description": accept.get("description", ""),
    }


@register_function(config_type=FetchPaidApiConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def fetch_paid_api_tool(config: FetchPaidApiConfig, builder: Builder):
    """Fetch data from a URL, handling x402 payment negotiation if required."""

    # Initialize the wallet signer based on config
    wallet = create_wallet_signer(signer_url=config.wallet_signer_url or None)

    class FetchInput(BaseModel):
        url: str = Field(description="The URL to fetch data from")

    async def _fetch_with_payment(url: str) -> str:
        """
        Fetch data from a URL that may require x402 payment.

        If the API responds with HTTP 402 (Payment Required), this tool will:
        1. Parse the x402 payment requirements
        2. Check against the agent's spending policy
        3. Sign and submit payment if approved
        4. Retry and return the data

        Use this when you need to access paid or premium data sources.
        """
        # spending state accessed via _spend_state dict

        try:
            async with httpx.AsyncClient(timeout=config.request_timeout) as client:
                # Initial request
                response = await client.get(url)

                # No payment needed
                if response.status_code != 402:
                    if response.status_code == 200:
                        try:
                            return json.dumps({"status": "success", "data": response.json()}, indent=2)
                        except (json.JSONDecodeError, ValueError):
                            return json.dumps({"status": "success", "data": response.text[:2000]}, indent=2)
                    return json.dumps(
                        {
                            "status": "error",
                            "http_status": response.status_code,
                            "error": f"HTTP {response.status_code}",
                        },
                        indent=2)

                # Parse 402 payment requirements
                payment_req = _parse_x402_requirements(response)
                if not payment_req:
                    return json.dumps(
                        {
                            "status": "error",
                            "error": "Received HTTP 402 but could not parse x402 payment requirements",
                        },
                        indent=2)

                amount = payment_req["amount"]
                recipient = payment_req["recipient"]

                logger.info(
                    "402 Payment Required: %.4f USDC to %s (%s)",
                    amount,
                    recipient[:10] + "...",
                    payment_req.get("description", ""),
                )

                # Check spending policy
                allowed, reason = _check_spending_policy(
                    amount, recipient,
                    config.max_per_transaction,
                    config.max_daily_spend,
                    config.allowed_recipients,
                )
                if not allowed:
                    _payment_log.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "url": url,
                        "amount": amount,
                        "recipient": recipient,
                        "status": "denied",
                        "reason": reason,
                    })
                    return json.dumps(
                        {
                            "status": "payment_denied",
                            "amount": amount,
                            "reason": reason,
                            "daily_spent": _spend_state["daily_spent"],
                            "daily_limit": config.max_daily_spend,
                        },
                        indent=2)

                # Sign payment via wallet signer
                try:
                    payment_proof = wallet.sign_payment(
                        amount=payment_req["raw_amount"],
                        recipient=recipient,
                        asset=payment_req.get("asset", ""),
                        network=payment_req.get("network", "base"),
                    )
                except Exception as e:
                    _payment_log.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "url": url,
                        "amount": amount,
                        "recipient": recipient,
                        "status": "signing_failed",
                        "reason": str(e),
                    })
                    return json.dumps({
                        "status": "error",
                        "error": f"Payment signing failed: {e}",
                    }, indent=2)

                # Retry with payment proof
                retry_response = await client.get(url, headers={
                    "X-PAYMENT": payment_proof["header"],
                })

                if retry_response.status_code == 200:
                    _spend_state["daily_spent"] += amount
                    tx_hash = payment_proof.get("tx_hash", "")
                    _payment_log.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "url": url,
                        "amount": amount,
                        "recipient": recipient,
                        "status": "success",
                        "tx_hash": tx_hash,
                    })
                    logger.info("Payment successful: %.4f USDC (tx: %s)", amount, tx_hash[:16])
                    try:
                        data = retry_response.json()
                    except (json.JSONDecodeError, ValueError):
                        data = retry_response.text[:2000]
                    return json.dumps(
                        {
                            "status": "success",
                            "data": data,
                            "payment": {
                                "amount": amount, "tx_hash": tx_hash
                            },
                        },
                        indent=2)
                else:
                    _payment_log.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "url": url,
                        "amount": amount,
                        "recipient": recipient,
                        "status": "retry_failed",
                        "reason": f"HTTP {retry_response.status_code}",
                    })
                    return json.dumps(
                        {
                            "status": "error",
                            "error": f"Payment sent but data request failed: HTTP {retry_response.status_code}",
                        },
                        indent=2)

        except httpx.TimeoutException:
            return json.dumps({
                "status": "error", "error": f"Request timed out after {config.request_timeout}s"
            },
                              indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)}, indent=2)

    yield FunctionInfo.from_fn(
        _fetch_with_payment,
        input_schema=FetchInput,
        description=("Fetch data from a URL that may require x402 payment. "
                     "Handles HTTP 402 responses by negotiating payment via the x402 protocol. "
                     "Spending is bounded by configurable per-transaction and daily limits."),
    )


@register_function(config_type=GetPaymentStatusConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def get_payment_status_tool(config: GetPaymentStatusConfig, builder: Builder):
    """Get the current spending status and recent payment history."""

    class StatusInput(BaseModel):
        detail_level: str = Field(
            default="summary",
            description="Level of detail: 'summary' for totals only, 'full' for recent transactions",
        )

    async def _get_status(detail_level: str = "summary") -> str:
        """
        Get the current payment spending status and recent transaction history.

        Use this to check how much budget remains before making paid API calls.
        """
        # spending state accessed via _spend_state dict

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_payments = [p for p in _payment_log if p["timestamp"].startswith(today)]

        result = {
            "daily_spent": _spend_state["daily_spent"],
            "today_transactions": len(today_payments),
        }
        if detail_level == "full":
            result["recent_payments"] = today_payments[-5:]

        return json.dumps(result, indent=2)

    yield FunctionInfo.from_fn(
        _get_status,
        input_schema=StatusInput,
        description="Get the current payment spending status and recent transaction history",
    )
