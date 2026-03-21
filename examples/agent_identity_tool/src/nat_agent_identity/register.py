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
Agent Identity & Reputation Tool for NeMo Agent Toolkit.

Provides on-chain agent identity verification using ERC-8004 registries.
Before transacting with or delegating to another agent, this tool lets
your agent verify:
  1. The other agent has a registered on-chain identity (ERC-721 token)
  2. Their reputation score meets a configurable threshold
  3. Their service endpoints and capabilities match expectations
  4. They have not been flagged or had their identity revoked

This is the trust layer that enables safe agent-to-agent interactions.
"""

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel
from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.builder import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class VerifyAgentIdentityConfig(FunctionBaseConfig, name="verify_agent_identity"):
    """Configuration for the agent identity verification tool."""

    registry_url: str = Field(
        default="http://localhost:8500",
        description="URL of the identity registry service",
    )
    min_reputation_score: float = Field(
        default=0.0,
        description="Minimum reputation score (0-100) to consider an agent trustworthy",
    )
    required_capabilities: list[str] = Field(
        default_factory=list,
        description="Required capabilities the target agent must advertise",
    )
    chain: str = Field(
        default="base",
        description="Blockchain network for identity lookups (base, ethereum, arbitrum)",
    )
    request_timeout: float = Field(
        default=15.0,
        description="HTTP request timeout for registry queries",
    )


class LookupReputationConfig(FunctionBaseConfig, name="lookup_agent_reputation"):
    """Configuration for the reputation lookup tool."""

    registry_url: str = Field(
        default="http://localhost:8500",
        description="URL of the identity registry service",
    )
    chain: str = Field(
        default="base",
        description="Blockchain network for reputation lookups",
    )
    request_timeout: float = Field(
        default=15.0,
        description="HTTP request timeout for registry queries",
    )


def _format_identity(data: dict[str, Any]) -> str:
    """Format agent identity data into a readable summary."""
    lines = []
    lines.append(f"Agent ID: {data.get('agent_id', 'unknown')}")
    lines.append(f"Owner: {data.get('owner', 'unknown')}")
    lines.append(f"Registered: {data.get('registered_at', 'unknown')}")

    uri = data.get("agent_uri", "")
    if uri:
        lines.append(f"Agent URI: {uri}")

    capabilities = data.get("capabilities", [])
    if capabilities:
        lines.append(f"Capabilities: {', '.join(capabilities)}")

    endpoints = data.get("service_endpoints", [])
    if endpoints:
        lines.append("Service Endpoints:")
        for ep in endpoints:
            lines.append(f"  - {ep.get('type', '?')}: {ep.get('url', '?')}")

    metadata = data.get("metadata", {})
    if metadata:
        lines.append("Metadata:")
        for key, value in metadata.items():
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)


def _format_reputation(data: dict[str, Any]) -> str:
    """Format reputation data into a readable summary."""
    lines = []
    lines.append(f"Agent ID: {data.get('agent_id', 'unknown')}")
    lines.append(f"Overall Score: {data.get('overall_score', 0):.1f}/100")
    lines.append(f"Total Reviews: {data.get('total_reviews', 0)}")
    lines.append(f"Positive: {data.get('positive_count', 0)}")
    lines.append(f"Negative: {data.get('negative_count', 0)}")

    categories = data.get("category_scores", {})
    if categories:
        lines.append("Category Scores:")
        for cat, score in categories.items():
            lines.append(f"  {cat}: {score:.1f}/100")

    recent = data.get("recent_feedback", [])
    if recent:
        lines.append(f"Recent Feedback ({len(recent)} entries):")
        for fb in recent[:5]:
            score = fb.get("score", 0)
            comment = fb.get("comment", "")[:80]
            client = fb.get("client", "unknown")[:10]
            lines.append(f"  [{score:+d}] {comment} (from {client}...)")

    return "\n".join(lines)


@register_function(
    config_type=VerifyAgentIdentityConfig,
    framework_wrappers=[LLMFrameworkEnum.LANGCHAIN],
)
async def verify_agent_identity(config: VerifyAgentIdentityConfig, builder: Builder):
    """Verify an agent's on-chain identity and reputation."""

    class VerifyInput(BaseModel):
        agent_address: str = Field(description="Ethereum address or agent ID to verify")

    async def _verify(agent_address: str) -> str:
        """
        Verify the identity and reputation of an agent by their address.

        Args:
            agent_address: The Ethereum address or agent ID to verify.

        Returns:
            Identity details, reputation summary, and trust recommendation.
        """
        results = {
            "identity": None,
            "reputation": None,
            "trust_decision": "UNKNOWN",
            "reasons": [],
        }

        try:
            async with httpx.AsyncClient(timeout=config.request_timeout) as client:
                # Step 1: Look up identity
                logger.info("Verifying identity for %s on %s", agent_address[:10] + "...", config.chain)

                identity_resp = await client.get(
                    f"{config.registry_url}/identity/{agent_address}",
                    params={"chain": config.chain},
                )

                if identity_resp.status_code == 404:
                    results["trust_decision"] = "REJECT"
                    results["reasons"].append("No on-chain identity found for this address")
                    return json.dumps(results, indent=2)

                identity_resp.raise_for_status()
                identity = identity_resp.json()
                results["identity"] = identity

                # Step 2: Check reputation
                rep_resp = await client.get(
                    f"{config.registry_url}/reputation/{agent_address}",
                    params={"chain": config.chain},
                )

                if rep_resp.status_code == 200:
                    reputation = rep_resp.json()
                    results["reputation"] = reputation

                    score = reputation.get("overall_score", 0)
                    if score < config.min_reputation_score:
                        results["trust_decision"] = "REJECT"
                        results["reasons"].append(f"Reputation score {score:.1f} below threshold"
                                                  f" {config.min_reputation_score:.1f}")
                    else:
                        results["reasons"].append(f"Reputation score {score:.1f} meets threshold"
                                                  f" {config.min_reputation_score:.1f}")

                # Step 3: Check required capabilities
                if config.required_capabilities:
                    agent_caps = set(identity.get("capabilities", []))
                    required = set(config.required_capabilities)
                    missing = required - agent_caps
                    if missing:
                        results["trust_decision"] = "REJECT"
                        results["reasons"].append(f"Missing required capabilities: "
                                                  f"{', '.join(missing)}")
                    else:
                        results["reasons"].append("All required capabilities present")

                # Step 4: Check if identity is active (not revoked)
                if identity.get("revoked", False):
                    results["trust_decision"] = "REJECT"
                    results["reasons"].append("Agent identity has been revoked")
                elif identity.get("expired", False):
                    results["trust_decision"] = "REJECT"
                    results["reasons"].append("Agent identity has expired")

                # Final trust decision
                if results["trust_decision"] != "REJECT":
                    results["trust_decision"] = "TRUST"

        except httpx.ConnectError:
            results["trust_decision"] = "ERROR"
            results["reasons"].append(f"Cannot reach identity registry at {config.registry_url}")
        except httpx.HTTPStatusError as e:
            results["trust_decision"] = "ERROR"
            results["reasons"].append(f"Registry returned error: {e.response.status_code}")
        except Exception as e:
            results["trust_decision"] = "ERROR"
            results["reasons"].append(f"Verification failed: {str(e)}")

        # Build human-readable summary
        summary_parts = []
        summary_parts.append(f"Trust Decision: {results['trust_decision']}")

        if results["identity"]:
            summary_parts.append("\n--- Identity ---")
            summary_parts.append(_format_identity(results["identity"]))

        if results["reputation"]:
            summary_parts.append("\n--- Reputation ---")
            summary_parts.append(_format_reputation(results["reputation"]))

        if results["reasons"]:
            summary_parts.append("\n--- Reasons ---")
            for reason in results["reasons"]:
                summary_parts.append(f"  - {reason}")

        return "\n".join(summary_parts)

    yield FunctionInfo.from_fn(
        _verify,
        description=("Verify an agent's on-chain identity and reputation using "
                     "ERC-8004 registries. Returns identity details, reputation "
                     "score, and a trust recommendation (TRUST/REJECT/ERROR). "
                     "Use before delegating tasks or transacting with unknown agents."),
    )


@register_function(
    config_type=LookupReputationConfig,
    framework_wrappers=[LLMFrameworkEnum.LANGCHAIN],
)
async def lookup_agent_reputation(config: LookupReputationConfig, builder: Builder):
    """Look up an agent's reputation history and feedback details."""

    class ReputationInput(BaseModel):
        agent_address: str = Field(description="Ethereum address or agent ID to look up")
        category: str = Field(default="",
                              description=("Optional category filter (e.g., accuracy, reliability,"
                                           " speed). Empty returns all categories."))

    async def _lookup(agent_address: str, category: str = "") -> str:
        """
        Look up detailed reputation data for an agent.

        Args:
            agent_address: The Ethereum address or agent ID to look up.
            category: Optional category filter (e.g., "accuracy",
                "reliability", "speed"). Empty string returns all.

        Returns:
            Detailed reputation summary with category scores and
            recent feedback entries.
        """
        try:
            async with httpx.AsyncClient(timeout=config.request_timeout) as client:
                params: dict[str, str] = {"chain": config.chain}
                if category:
                    params["category"] = category

                resp = await client.get(
                    f"{config.registry_url}/reputation/{agent_address}",
                    params=params,
                )

                if resp.status_code == 404:
                    return (f"No reputation data found for {agent_address}. "
                            "This agent may not be registered on-chain.")

                resp.raise_for_status()
                data = resp.json()
                return _format_reputation(data)

        except httpx.ConnectError:
            return (f"Cannot reach reputation registry at "
                    f"{config.registry_url}")
        except Exception as e:
            return f"Reputation lookup failed: {str(e)}"

    yield FunctionInfo.from_fn(
        _lookup,
        description=("Look up detailed reputation data for an agent, including "
                     "overall score, category breakdowns, and recent feedback. "
                     "Use to evaluate an agent's track record before collaboration."),
    )
