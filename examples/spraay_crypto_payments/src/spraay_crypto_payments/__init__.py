# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

"""Spraay Crypto Payments — NeMo Agent Toolkit plugin.

Registers Spraay x402 gateway tools for use in NeMo Agent Toolkit workflows.
"""

from nat.components.functions.tool import tool
from nat.registry import register

from .spraay_tools import (
    spraay_balance,
    spraay_batch_send,
    spraay_chains,
    spraay_escrow_create,
    spraay_health,
    spraay_price,
    spraay_routes,
    spraay_rtp_discover,
)


@register("spraay_health")
def _register_health(**kwargs):
    return tool(spraay_health, description=kwargs.get("description", ""))


@register("spraay_routes")
def _register_routes(**kwargs):
    return tool(spraay_routes, description=kwargs.get("description", ""))


@register("spraay_chains")
def _register_chains(**kwargs):
    return tool(spraay_chains, description=kwargs.get("description", ""))


@register("spraay_balance")
def _register_balance(**kwargs):
    return tool(spraay_balance, description=kwargs.get("description", ""))


@register("spraay_price")
def _register_price(**kwargs):
    return tool(spraay_price, description=kwargs.get("description", ""))


@register("spraay_batch_send")
def _register_batch_send(**kwargs):
    return tool(spraay_batch_send, description=kwargs.get("description", ""))


@register("spraay_escrow_create")
def _register_escrow_create(**kwargs):
    return tool(spraay_escrow_create, description=kwargs.get("description", ""))


@register("spraay_rtp_discover")
def _register_rtp_discover(**kwargs):
    return tool(spraay_rtp_discover, description=kwargs.get("description", ""))
