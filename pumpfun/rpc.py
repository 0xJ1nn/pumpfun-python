"""
Minimal async JSON-RPC helper + token-program detection.

A single ``httpx`` POST against any Solana RPC endpoint — bring your own
(Helius, QuickNode, Triton, or the rate-limited public node).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from solders.pubkey import Pubkey

from .constants import TOKEN_2022_PROGRAM, TOKEN_PROGRAM


async def rpc_call(
    rpc_url: str,
    method: str,
    params: list[Any],
    *,
    http_client: httpx.AsyncClient | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Make a single JSON-RPC call and return the ``result`` object."""
    should_close = http_client is None
    client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(timeout))
    try:
        resp = await client.post(
            rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        resp.raise_for_status()
        data = resp.json()
    finally:
        if should_close:
            await client.aclose()
    result = data.get("result", {})
    return result if isinstance(result, dict) else {}


async def detect_token_program(
    rpc_url: str,
    mint: Pubkey,
    *,
    http_client: httpx.AsyncClient | None = None,
    retries: int = 3,
) -> Pubkey:
    """Return the owning token program of a mint (SPL Token vs Token-2022).

    Retries on transient RPC failure and falls back to Token-2022, since
    virtually all new pump.fun mints are Token-2022.
    """
    for attempt in range(retries):
        try:
            result = await rpc_call(
                rpc_url, "getAccountInfo", [str(mint), {"encoding": "base64"}],
                http_client=http_client,
            )
            value = result.get("value") if isinstance(result, dict) else None
            if value:
                owner = value.get("owner", "")
                if owner == str(TOKEN_2022_PROGRAM):
                    return TOKEN_2022_PROGRAM
                if owner == str(TOKEN_PROGRAM):
                    return TOKEN_PROGRAM
        except httpx.HTTPError:
            pass
        if attempt < retries - 1:
            await asyncio.sleep(0.5 * (attempt + 1))
    return TOKEN_2022_PROGRAM
