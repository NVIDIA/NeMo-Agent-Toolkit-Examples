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
"""Standalone smoke test for the Spraay batch_send x402 flow.

Drives ``SpraayClient`` directly against the gateway's ``/api/v1/batch/execute``
endpoint, bypassing the ReAct agent entirely. No LLM, no NVIDIA_API_KEY, and no
tool-selection ambiguity — exactly one batch payment is attempted, so this is
the most deterministic way to run a first live test.

Modes (identical to the tools):

* **Dry-run** (no ``EVM_PRIVATE_KEY``): prints the x402 payment quote. No funds
  move. Run this first to sanity-check connectivity and your recipient list.
* **Live** (``EVM_PRIVATE_KEY`` set): signs and settles the x402 gateway fee and
  submits the batch. THIS MOVES REAL FUNDS. Requires an explicit confirmation
  (type ``yes`` at the prompt, or pass ``--yes``).

Examples
--------
Dry-run the default single-recipient batch::

    python scripts/live_batch_send_smoke.py

Live send 0.01 USDC on Base to one address (requires a funded wallet)::

    export EVM_PRIVATE_KEY=0x...        # funded Base wallet; never commit/share
    python scripts/live_batch_send_smoke.py \
        --to 0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8 --amount 0.01 --yes

Multiple recipients::

    python scripts/live_batch_send_smoke.py \
        --to 0xAAA...:0.01 --to 0xBBB...:0.02 --yes

The private key is read only from the environment, used only to build the
in-memory signer, and is never printed by this script.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# Allow running straight from the example directory without `pip install -e .`.
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from spraay_crypto_payments.spraay_client import SpraayClient, to_batch_execute_payload  # noqa: E402

# Zero-address placeholder used for dry-run quotes (mirrors the batch_send tool).
_PLACEHOLDER_SENDER = "0x0000000000000000000000000000000000000000"


def _parse_recipients(values: list[str]) -> list[dict]:
    """Parse --to values into recipient dicts.

    Each value is either a bare address (paired with --amount) or the compact
    ``address:amount`` form. Returns a list of {"to", "amount"} dicts.
    """
    recipients: list[dict] = []
    for value in values:
        if ":" in value:
            addr, _, amount = value.partition(":")
            recipients.append({"to": addr.strip(), "amount": amount.strip()})
        else:
            recipients.append({"to": value.strip(), "amount": None})
    return recipients


def _derive_sender(private_key: str) -> str | None:
    """Derive the payer's public address from the private key, or None.

    Never logs or returns the key itself — only the derived public address.
    """
    try:
        from eth_account import Account
    except ImportError:
        return None
    key = private_key if private_key.startswith("0x") else "0x" + private_key
    try:
        return Account.from_key(key).address
    except Exception:
        # Invalid key — let SpraayClient surface the structured error at send time.
        return None


def _build_batch(args: argparse.Namespace, private_key: str | None) -> dict:
    """Construct the /api/v1/batch/execute request body."""
    recipients = _parse_recipients(args.to)
    # Fill in the shared --amount for any bare addresses.
    for rec in recipients:
        if rec["amount"] is None:
            if args.amount is None:
                raise SystemExit(
                    f"Recipient {rec['to']} has no amount. Pass --amount, or use "
                    f"the address:amount form."
                )
            rec["amount"] = args.amount

    data: dict = {
        "recipients": recipients,
        "token": args.token,
        "chain": args.chain,
    }

    # In live mode the sender must be the paying wallet, not the dry-run
    # placeholder. Prefer an explicit --sender, else derive it from the key.
    if args.sender:
        data["sender"] = args.sender
    elif private_key:
        derived = _derive_sender(private_key)
        data["sender"] = derived or _PLACEHOLDER_SENDER
    else:
        data["sender"] = _PLACEHOLDER_SENDER

    return data


def _confirm(data: dict, live: bool, assume_yes: bool) -> bool:
    """Print a summary and, in live mode, require explicit confirmation."""
    total = 0.0
    for rec in data["recipients"]:
        try:
            total += float(rec["amount"])
        except (TypeError, ValueError):
            total = float("nan")
            break

    print("=" * 64)
    print("Spraay batch_send smoke test")
    print("=" * 64)
    print(f"  mode        : {'LIVE (moves real funds)' if live else 'dry-run (quote only)'}")
    print(f"  gateway     : {data.get('_gateway', '(default)')}")
    print(f"  token/chain : {data['token']} on {data['chain']}")
    print(f"  sender      : {data['sender']}")
    print(f"  recipients  : {len(data['recipients'])}")
    for rec in data["recipients"]:
        print(f"      -> {rec['to']}  {rec['amount']} {data['token']}")
    print(f"  total send  : {total} {data['token']} (plus the $0.02 x402 gateway fee)")
    print("=" * 64)

    if not live:
        return True
    if assume_yes:
        print("Confirmation skipped via --yes. Proceeding with a REAL payment.\n")
        return True
    try:
        answer = input("This will move REAL funds. Type 'yes' to proceed: ").strip().lower()
    except EOFError:
        answer = ""
    return answer == "yes"


async def _run(args: argparse.Namespace) -> int:
    private_key = os.environ.get("EVM_PRIVATE_KEY")
    live = bool(private_key)

    data = _build_batch(args, private_key)
    summary = dict(data, _gateway=args.gateway)

    if not _confirm(summary, live, args.yes):
        print("Aborted - no request sent.")
        return 1

    client = SpraayClient(gateway_url=args.gateway, timeout=args.timeout)
    print("\nSubmitting batch to", f"{args.gateway}/api/v1/batch/execute", "...\n")
    # The execute endpoint requires parallel recipients/amounts arrays in raw
    # base units (see its 402 bazaar schema), not the {to, amount} decimal
    # objects used for display/confirmation above.
    payload = to_batch_execute_payload(data)
    result = await client.post("/api/v1/batch/execute", payload)
    print(result)

    # Best-effort exit code: non-zero if the client reported an error.
    try:
        parsed = json.loads(result)
    except Exception:
        return 0
    if isinstance(parsed, dict) and parsed.get("error"):
        return 2
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic smoke test for the Spraay batch_send x402 flow.",
    )
    parser.add_argument(
        "--to",
        action="append",
        default=[],
        metavar="ADDRESS[:AMOUNT]",
        help="Recipient address, or address:amount. Repeatable. "
        "Defaults to one small test recipient.",
    )
    parser.add_argument(
        "--amount",
        default=None,
        help="Amount per recipient for bare --to addresses (default: 0.01 when "
        "no recipients are given).",
    )
    parser.add_argument("--token", default="USDC", help="Token symbol (default: USDC).")
    parser.add_argument("--chain", default="base", help="Chain (default: base).")
    parser.add_argument(
        "--sender",
        default=None,
        help="Sender/payer address. In live mode, defaults to the address "
        "derived from EVM_PRIVATE_KEY.",
    )
    parser.add_argument(
        "--gateway",
        default=os.environ.get("SPRAAY_GATEWAY_URL", "https://gateway.spraay.app"),
        help="Gateway base URL (default: $SPRAAY_GATEWAY_URL or gateway.spraay.app).",
    )
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds (default: 60).")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the live-mode confirmation prompt (use with care).",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if not args.to:
        # Default: a single tiny test payment to a well-known example address.
        args.to = ["0xAd62f03C7514bb8c51f1eA70C2b75C37404695c8"]
        if args.amount is None:
            args.amount = "0.01"
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
