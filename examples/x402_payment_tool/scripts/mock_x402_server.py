#!/usr/bin/env python3
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
Mock x402 server for testing the payment tool.

Simulates a paid API that:
- Returns 402 with x402 payment requirements for unauthenticated requests
- Returns 200 with mock data when valid payment proof is provided

Usage:
    python scripts/mock_x402_server.py
    # Server runs on http://localhost:8402
"""

import json
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

MOCK_DATA = {
    "market_data": {
        "symbol": "NVDA",
        "price": 142.50,
        "volume": 45_000_000,
        "change_24h": 3.2,
        "source": "premium-data-provider",
        "timestamp": "2026-03-18T12:00:00Z",
    }
}

PAYMENT_REQUIREMENTS = {
    "x402Version":
        1,
    "accepts": [{
        "scheme": "exact",
        "network": "base",
        "maxAmountRequired": "50000",  # 0.05 USDC (6 decimals)
        "resource": "http://localhost:8402/v1/market-data",
        "description": "Premium market data access",
        "mimeType": "application/json",
        "payTo": "0x1234567890abcdef1234567890abcdef12345678",
        "maxTimeoutSeconds": 300,
        "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
    }],
}

MOCK_RECIPIENT = "0x1234567890abcdef1234567890abcdef12345678"


class X402Handler(BaseHTTPRequestHandler):

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/v1/market-data"):
            payment_header = self.headers.get("X-PAYMENT", "")

            if payment_header:
                # Validate payment proof (mock: just check it's non-empty JSON)
                try:
                    payment = json.loads(payment_header)
                    if payment.get("payTo") == MOCK_RECIPIENT:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(MOCK_DATA).encode())
                        return
                except (json.JSONDecodeError, KeyError):
                    pass

                # Invalid payment
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid payment proof"}).encode())
                return

            # No payment — return 402
            self.send_response(402)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(PAYMENT_REQUIREMENTS).encode())
            return

        # 404 for unknown paths
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[x402-mock] {args[0]}")


def main():
    port = 8402
    server = HTTPServer(("localhost", port), X402Handler)
    print(f"Mock x402 server running on http://localhost:{port}")
    print("  GET /v1/market-data → 402 (requires payment)")
    print("  GET /v1/market-data + X-PAYMENT header → 200 (mock data)")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
