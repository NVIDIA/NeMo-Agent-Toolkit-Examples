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
"""
Mock ERC-8004 Identity & Reputation Registry Server.

Simulates on-chain identity lookups and reputation queries for testing
the agent identity verification tool without requiring a live blockchain.

Usage:
    python scripts/mock_registry_server.py
    # Server runs on http://localhost:8500
"""

import json
import logging
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from urllib.parse import parse_qs
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock agent registry - simulates on-chain data
MOCK_AGENTS = {
    "0x1234567890abcdef1234567890abcdef12345678": {
        "agent_id": 42,
        "owner": "0xaaaa000000000000000000000000000000000001",
        "registered_at": "2026-01-15T10:30:00Z",
        "agent_uri": "agent://market-data-provider.eth",
        "capabilities": ["market-data", "historical-quotes", "real-time-pricing"],
        "service_endpoints": [
            {
                "type": "x402-api",
                "url": "https://api.example.com/v1/market-data",
            },
            {
                "type": "websocket",
                "url": "wss://ws.example.com/stream",
            },
        ],
        "metadata": {
            "model": "gpt-4-turbo",
            "framework": "NeMo Agent Toolkit",
            "version": "1.4.0",
        },
        "revoked": False,
        "expired": False,
    },
    "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef": {
        "agent_id": 99,
        "owner": "0xbbbb000000000000000000000000000000000002",
        "registered_at": "2026-02-20T14:00:00Z",
        "agent_uri": "agent://untrusted-bot.eth",
        "capabilities": ["text-generation"],
        "service_endpoints": [],
        "metadata": {
            "model": "unknown",
        },
        "revoked": True,
        "expired": False,
    },
    "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
        "agent_id": 7,
        "owner": "0xcccc000000000000000000000000000000000003",
        "registered_at": "2025-12-01T08:00:00Z",
        "agent_uri": "agent://expired-agent.eth",
        "capabilities": ["translation"],
        "service_endpoints": [],
        "metadata": {},
        "revoked": False,
        "expired": True,
    },
}

# Mock reputation data
MOCK_REPUTATION = {
    "0x1234567890abcdef1234567890abcdef12345678": {
        "agent_id":
            42,
        "overall_score":
            87.5,
        "total_reviews":
            156,
        "positive_count":
            142,
        "negative_count":
            14,
        "category_scores": {
            "accuracy": 92.0,
            "reliability": 88.5,
            "speed": 79.0,
            "cost_efficiency": 85.0,
        },
        "recent_feedback": [
            {
                "score": 5,
                "comment": "Accurate market data, fast response times",
                "client": "0xfeed000001",
                "timestamp": "2026-03-19T16:00:00Z",
            },
            {
                "score": 4,
                "comment": "Good data quality, slightly slow during peak",
                "client": "0xfeed000002",
                "timestamp": "2026-03-18T09:30:00Z",
            },
            {
                "score": -2,
                "comment": "Returned stale data for NVDA after hours",
                "client": "0xfeed000003",
                "timestamp": "2026-03-15T22:00:00Z",
            },
        ],
    },
    "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef": {
        "agent_id":
            99,
        "overall_score":
            12.0,
        "total_reviews":
            8,
        "positive_count":
            1,
        "negative_count":
            7,
        "category_scores": {
            "accuracy": 10.0,
            "reliability": 15.0,
        },
        "recent_feedback": [{
            "score": -5,
            "comment": "Returned fabricated data",
            "client": "0xfeed000004",
            "timestamp": "2026-02-25T12:00:00Z",
        }, ],
    },
}

PORT = 8500


class RegistryHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock identity registry."""

    def do_GET(self):
        """Handle GET requests for identity and reputation lookups."""
        parsed = urlparse(self.path)
        path_parts = parsed.path.strip("/").split("/")
        params = parse_qs(parsed.query)

        if len(path_parts) == 2 and path_parts[0] == "identity":
            self._handle_identity(path_parts[1], params)
        elif len(path_parts) == 2 and path_parts[0] == "reputation":
            self._handle_reputation(path_parts[1], params)
        elif parsed.path == "/health":
            self._respond(200, {"status": "ok", "agents": len(MOCK_AGENTS)})
        else:
            self._respond(404, {"error": "Not found"})

    def _handle_identity(self, address: str, params: dict):
        """Look up agent identity."""
        address = address.lower()
        agent = None
        for addr, data in MOCK_AGENTS.items():
            if addr.lower() == address:
                agent = data
                break

        if agent is None:
            self._respond(404, {"error": "Agent not found"})
            return

        chain = params.get("chain", ["base"])[0]
        logger.info("Identity lookup: %s on %s", address[:10], chain)
        self._respond(200, agent)

    def _handle_reputation(self, address: str, params: dict):
        """Look up agent reputation."""
        address = address.lower()
        rep = None
        for addr, data in MOCK_REPUTATION.items():
            if addr.lower() == address:
                rep = data
                break

        if rep is None:
            self._respond(404, {"error": "No reputation data"})
            return

        category = params.get("category", [None])[0]

        if category and category in rep.get("category_scores", {}):
            filtered = {
                **rep,
                "category_scores": {
                    category: rep["category_scores"][category]
                },
            }
            self._respond(200, filtered)
        else:
            self._respond(200, rep)

    def _respond(self, status: int, data: dict):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def log_message(self, format, *args):
        """Suppress default access logs, use our logger instead."""
        logger.debug(format, *args)


def main():
    """Start the mock registry server."""
    server = HTTPServer(("0.0.0.0", PORT), RegistryHandler)
    logger.info("Mock ERC-8004 registry running on http://localhost:%d", PORT)
    logger.info("Test agents:")
    logger.info("  Trusted:  0x1234567890abcdef1234567890abcdef12345678")
    logger.info("  Revoked:  0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
    logger.info("  Expired:  0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    logger.info("  Unknown:  0x0000000000000000000000000000000000000000")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down registry server")
        server.shutdown()


if __name__ == "__main__":
    main()
