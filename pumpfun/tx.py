"""
Transaction assembly helpers.

Build an **unsigned** ``MessageV0`` (compute budget prepended, blockhash set):

    msg = build_message(payer, plan.instructions, blockhash)
    tx = VersionedTransaction(msg, [keypair])   # caller signs

Signing and submission are intentionally out of scope.
"""

from __future__ import annotations

import httpx
from solders.compute_budget import (
    set_compute_unit_limit,
    set_compute_unit_price,
)
from solders.hash import Hash
from solders.instruction import Instruction
from solders.message import MessageV0
from solders.pubkey import Pubkey

from .rpc import rpc_call

DEFAULT_COMPUTE_UNITS = 200_000
DEFAULT_COMPUTE_UNIT_PRICE = 200_000  # micro-lamports per CU


def prepend_compute_budget(
    instructions: list[Instruction],
    *,
    compute_units: int = DEFAULT_COMPUTE_UNITS,
    compute_unit_price: int = DEFAULT_COMPUTE_UNIT_PRICE,
) -> list[Instruction]:
    """Prepend SetComputeUnitLimit + SetComputeUnitPrice to an instruction list."""
    return [
        set_compute_unit_limit(compute_units),
        set_compute_unit_price(compute_unit_price),
        *instructions,
    ]


def build_message(
    payer: Pubkey,
    instructions: list[Instruction],
    recent_blockhash: Hash,
    *,
    compute_units: int = DEFAULT_COMPUTE_UNITS,
    compute_unit_price: int = DEFAULT_COMPUTE_UNIT_PRICE,
) -> MessageV0:
    """Compile a v0 message with compute budget prepended and the blockhash set."""
    ixs = prepend_compute_budget(
        instructions, compute_units=compute_units, compute_unit_price=compute_unit_price,
    )
    return MessageV0.try_compile(payer, ixs, [], recent_blockhash)


async def fetch_latest_blockhash(
    rpc_url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> Hash:
    """Fetch a recent blockhash for transaction assembly."""
    result = await rpc_call(
        rpc_url, "getLatestBlockhash", [{"commitment": "confirmed"}],
        http_client=http_client,
    )
    value = result.get("value") if isinstance(result, dict) else None
    blockhash = (value or {}).get("blockhash")
    if not blockhash:
        raise RuntimeError("getLatestBlockhash returned no blockhash")
    return Hash.from_string(blockhash)
