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

"""Mock paid API server for testing the x402 payment tool.

This server simulates an API that requires x402 payments:
- GET /data          → Returns 402 with payment requirements
- GET /data + X-Payment header → Returns premium data (200)
- GET /free          → Returns free data (200, no payment needed)

Usage:
    python scripts/mock_paid_api.py
    # Server runs on http://localhost:8402
"""

from __future__ import annotations

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

MOCK_RECIPIENT = "0x1234567890abcdef1234567890abcdef12345678"
MOCK_TOKEN = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base
PORT = 8402


class PaidAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler that simulates x402 payment flows."""

    def do_GET(self) -> None:
        if self.path == "/free":
            self._send_json(200, {"data": "This is free data. No payment required."})
            return

        if self.path == "/data":
            # Check for payment proof
            payment = self.headers.get("X-Payment")
            if payment:
                # Payment received — return premium data
                self._send_json(
                    200,
                    {
                        "data": {
                            "title": "Premium Market Analysis",
                            "summary": "BTC showing strong support at $84k with institutional "
                            "accumulation. ETH/BTC ratio recovering. AI token sector "
                            "outperforming market by 340% YTD.",
                            "confidence": 0.87,
                            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        },
                        "payment_status": "accepted",
                    },
                )
            else:
                # No payment — return 402 with x402 requirements
                self._send_json(
                    402,
                    {
                        "payment": {
                            "amount": 10000,  # 0.01 USDC (6 decimals)
                            "recipient": MOCK_RECIPIENT,
                            "token": MOCK_TOKEN,
                            "network": "base",
                            "description": "Premium market analysis report",
                            "nonce": uuid.uuid4().hex,
                            "expires_at": int(time.time()) + 300,
                        }
                    },
                )
            return

        self._send_json(404, {"error": "Not found"})

    def _send_json(self, status: int, body: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body, indent=2).encode())

    def log_message(self, format: str, *args: object) -> None:
        """Override to add payment status to logs."""
        print(f"[MOCK API] {args[0]}")


def main() -> None:
    server = HTTPServer(("localhost", PORT), PaidAPIHandler)
    print(f"Mock paid API running on http://localhost:{PORT}")
    print(f"  GET /data  → 402 (requires payment) or 200 (with payment)")
    print(f"  GET /free  → 200 (always free)")
    server.serve_forever()


if __name__ == "__main__":
    main()
