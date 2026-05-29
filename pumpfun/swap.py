"""
High-level bonding-curve buy/sell builders.

``build_buy`` / ``build_sell`` read the bonding curve, quote the trade, and
return an ordered list of **unsigned** instructions (ATA create + buy, or sell +
ATA close). You sign and send — keys never touch this library.

For graduated tokens (bonding curve complete), use the companion package
``pumpswap-python`` for the AMM pool swap.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey

from .bonding_curve import (
    PumpFunError,
    build_buy_instruction,
    build_sell_instruction,
    calculate_buy_amount,
    calculate_sell_amount,
    fetch_bonding_curve_state,
    fetch_fee_recipient,
)
from .constants import ASSOCIATED_TOKEN_PROGRAM, SYSTEM_PROGRAM, TOKEN_PROGRAM
from .pda import get_associated_token_address, get_bonding_curve_pda
from .rpc import detect_token_program


@dataclass(slots=True)
class BuyPlan:
    """Result of :func:`build_buy` — unsigned instructions + buy quote."""

    instructions: list[Instruction]
    sol_in: int
    expected_tokens: int
    max_sol_cost: int


@dataclass(slots=True)
class SellPlan:
    """Result of :func:`build_sell` — unsigned instructions + sell quote."""

    instructions: list[Instruction]
    token_amount: int
    expected_sol_out: int
    min_sol_out: int


def build_create_ata_idempotent(
    payer: Pubkey,
    mint: Pubkey,
    ata: Pubkey,
    token_program: Pubkey = TOKEN_PROGRAM,
) -> Instruction:
    """createAssociatedTokenAccountIdempotent — no-op if the ATA already exists."""
    accounts = [
        AccountMeta(payer, is_signer=True, is_writable=True),
        AccountMeta(ata, is_signer=False, is_writable=True),
        AccountMeta(payer, is_signer=False, is_writable=False),
        AccountMeta(mint, is_signer=False, is_writable=False),
        AccountMeta(SYSTEM_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(token_program, is_signer=False, is_writable=False),
    ]
    return Instruction(ASSOCIATED_TOKEN_PROGRAM, bytes([1]), accounts)


def build_close_account(
    owner: Pubkey,
    token_account: Pubkey,
    token_program: Pubkey = TOKEN_PROGRAM,
) -> Instruction:
    """SPL Token CloseAccount — reclaim rent from an empty token ATA after a sell."""
    return Instruction(token_program, bytes([9]), [
        AccountMeta(token_account, is_signer=False, is_writable=True),
        AccountMeta(owner, is_signer=False, is_writable=True),
        AccountMeta(owner, is_signer=True, is_writable=False),
    ])


def _as_pubkey(value: str | Pubkey) -> Pubkey:
    return value if isinstance(value, Pubkey) else Pubkey.from_string(value)


async def build_buy(
    rpc_url: str,
    user: str | Pubkey,
    token_mint: str | Pubkey,
    sol_lamports: int,
    *,
    slippage_bps: int = 500,
    http_client: httpx.AsyncClient | None = None,
) -> BuyPlan:
    """Build an unsigned bonding-curve buy (SOL → token).

    Slippage is applied as a ceiling on SOL cost: the program buys exactly the
    expected token amount and fails if the cost exceeds ``max_sol_cost``.
    """
    user = _as_pubkey(user)
    token_mint = _as_pubkey(token_mint)
    bonding_curve = get_bonding_curve_pda(token_mint)

    state = await fetch_bonding_curve_state(rpc_url, token_mint, http_client=http_client)
    if state.complete:
        raise PumpFunError("Bonding curve complete — token graduated; use pumpswap-python")

    token_program = await detect_token_program(rpc_url, token_mint, http_client=http_client)
    fee_recipient = await fetch_fee_recipient(rpc_url, http_client=http_client)

    expected_tokens = calculate_buy_amount(
        sol_lamports, state.virtual_sol_reserves, state.virtual_token_reserves,
    )
    if expected_tokens <= 0:
        raise PumpFunError("Buy would yield 0 tokens — curve may be drained")

    max_sol_cost = (sol_lamports * (10_000 + slippage_bps)) // 10_000
    associated_user = get_associated_token_address(user, token_mint, token_program)

    create_ata_ix = build_create_ata_idempotent(user, token_mint, associated_user, token_program)
    buy_ix = build_buy_instruction(
        user=user, token_mint=token_mint, bonding_curve=bonding_curve,
        sol_amount_lamports=max_sol_cost, min_tokens_out=expected_tokens,
        creator=state.creator, fee_recipient=fee_recipient, token_program=token_program,
    )
    return BuyPlan([create_ata_ix, buy_ix], sol_lamports, expected_tokens, max_sol_cost)


async def build_sell(
    rpc_url: str,
    user: str | Pubkey,
    token_mint: str | Pubkey,
    token_amount: int,
    *,
    slippage_bps: int = 500,
    http_client: httpx.AsyncClient | None = None,
) -> SellPlan:
    """Build an unsigned bonding-curve sell (token → SOL), closing the ATA afterwards."""
    user = _as_pubkey(user)
    token_mint = _as_pubkey(token_mint)
    bonding_curve = get_bonding_curve_pda(token_mint)

    state = await fetch_bonding_curve_state(rpc_url, token_mint, http_client=http_client)
    if state.complete:
        raise PumpFunError("Bonding curve complete — token graduated; use pumpswap-python")

    token_program = await detect_token_program(rpc_url, token_mint, http_client=http_client)
    fee_recipient = await fetch_fee_recipient(rpc_url, http_client=http_client)

    expected_sol_out = calculate_sell_amount(
        token_amount, state.virtual_sol_reserves, state.virtual_token_reserves,
    )
    if expected_sol_out <= 0:
        raise PumpFunError("Sell would yield 0 SOL — curve may be drained")

    min_sol_out = (expected_sol_out * (10_000 - slippage_bps)) // 10_000
    sell_ix = build_sell_instruction(
        user=user, token_mint=token_mint, bonding_curve=bonding_curve,
        token_amount=token_amount, min_sol_output=min_sol_out,
        creator=state.creator, fee_recipient=fee_recipient, token_program=token_program,
    )
    token_ata = get_associated_token_address(user, token_mint, token_program)
    close_ix = build_close_account(user, token_ata, token_program)
    return SellPlan([sell_ix, close_ix], token_amount, expected_sol_out, min_sol_out)
