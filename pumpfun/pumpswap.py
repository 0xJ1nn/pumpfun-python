"""
PumpSwap AMM — constant-product pool swap instructions and on-chain state.

Supports both legacy PumpSwap (PSwapMdSai...) and Pump AMM (pAMMBay...) pools.
"""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass

import httpx
from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey

from .constants import (
    PUMP_AMM_PROGRAM,
    PUMP_SWAP_EVENT_AUTHORITY,
    PUMP_SWAP_FEE_RECIPIENT,
    PUMP_SWAP_GLOBAL_CONFIG,
    PUMP_SWAP_PROGRAM,
    PUMPSWAP_SWAP_DISCRIMINATOR,
    SOL_MINT,
    TOKEN_PROGRAM,
)


class PumpSwapError(Exception):
    """Raised when a PumpSwap operation fails."""


@dataclass(slots=True)
class PoolState:
    """Parsed on-chain PumpSwap/Pump AMM pool state."""

    pool_bump: int
    index: int
    creator: Pubkey
    coin_creator: Pubkey
    base_mint: Pubkey
    quote_mint: Pubkey
    lp_mint: Pubkey
    pool_base_token_account: Pubkey
    pool_quote_token_account: Pubkey
    lp_fee_basis_points: int
    protocol_fee_basis_points: int
    is_pump_amm: bool = False
    base_is_sol: bool = False


# ---------------------------------------------------------------------------
# Swap math (pure functions — no RPC needed)
# ---------------------------------------------------------------------------


def calculate_swap_output(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
    lp_fee_bps: int,
    protocol_fee_bps: int,
) -> tuple[int, int]:
    """
    Calculate output for a constant-product AMM swap.

    Fee is deducted from the input amount before computing swap.

    Args:
        amount_in: Input token amount.
        reserve_in: Reserve of the input token in the pool.
        reserve_out: Reserve of the output token in the pool.
        lp_fee_bps: LP fee in basis points.
        protocol_fee_bps: Protocol fee in basis points.

    Returns:
        Tuple of (amount_out, total_fee).
    """
    total_fee_bps = lp_fee_bps + protocol_fee_bps
    fee = (amount_in * total_fee_bps) // 10_000
    amount_in_after_fee = amount_in - fee

    if reserve_in + amount_in_after_fee == 0:
        return 0, fee

    amount_out = (reserve_out * amount_in_after_fee) // (reserve_in + amount_in_after_fee)
    return amount_out, fee


# ---------------------------------------------------------------------------
# On-chain state reading
# ---------------------------------------------------------------------------


async def fetch_pool_state(
    rpc_url: str,
    pool_address: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> PoolState:
    """
    Read a PumpSwap/Pump AMM pool account from on-chain.

    Layout (after 8-byte Anchor discriminator):
      - offset  8: pool_bump (u8)
      - offset  9: index (u16 LE)
      - offset 11: creator (Pubkey, 32B)
      - offset 43: base_mint (Pubkey, 32B)
      - offset 75: quote_mint (Pubkey, 32B)
      - offset 107: lp_mint (Pubkey, 32B)
      - offset 139: pool_base_token_account (Pubkey, 32B)
      - offset 171: pool_quote_token_account (Pubkey, 32B)
      - offset 203: lp_fee_basis_points (u64 LE) — legacy only
      - offset 211: protocol_fee_basis_points (u64 LE) — legacy only

    Args:
        rpc_url: Solana RPC endpoint URL.
        pool_address: Pool account address.
        http_client: Optional httpx client.

    Returns:
        PoolState with reserves, mints, and vault addresses.

    Raises:
        PumpSwapError: If the account can't be read or parsed.
    """
    should_close = http_client is None
    client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    try:
        resp = await client.post(rpc_url, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [pool_address, {"encoding": "base64"}],
        })
        resp.raise_for_status()
        data = resp.json()
    finally:
        if should_close:
            await client.aclose()

    result = data.get("result", {})
    value = result.get("value")
    if not value:
        raise PumpSwapError(f"Pool account {pool_address} not found")

    raw_data = value.get("data", [])
    if not isinstance(raw_data, list) or not raw_data:
        raise PumpSwapError("Cannot decode pool account data")

    account_bytes = base64.b64decode(raw_data[0])
    if len(account_bytes) < 219:
        raise PumpSwapError(f"Pool data too short: {len(account_bytes)} bytes (need >= 219)")

    owner = value.get("owner", "")
    valid_owners = {str(PUMP_SWAP_PROGRAM), str(PUMP_AMM_PROGRAM)}
    if owner and owner not in valid_owners:
        raise PumpSwapError(f"Account owned by {owner}, not PumpSwap/PumpAMM program")

    is_pump_amm = owner == str(PUMP_AMM_PROGRAM)

    def _pubkey_at(offset: int) -> Pubkey:
        return Pubkey.from_bytes(account_bytes[offset: offset + 32])

    pool_bump = account_bytes[8]
    index = struct.unpack_from("<H", account_bytes, 9)[0]
    creator = _pubkey_at(11)
    base_mint = _pubkey_at(43)
    quote_mint = _pubkey_at(75)
    lp_mint = _pubkey_at(107)
    pool_base_token_account = _pubkey_at(139)
    pool_quote_token_account = _pubkey_at(171)

    if is_pump_amm:
        lp_fee_basis_points = 200
        protocol_fee_basis_points = 100
        coin_creator = Pubkey.default()
        if len(account_bytes) >= 243:
            coin_creator = _pubkey_at(211)
    else:
        lp_fee_basis_points = struct.unpack_from("<Q", account_bytes, 203)[0]
        protocol_fee_basis_points = struct.unpack_from("<Q", account_bytes, 211)[0]
        coin_creator = creator

    base_is_sol = is_pump_amm and str(base_mint) == str(SOL_MINT)

    return PoolState(
        pool_bump=pool_bump,
        index=index,
        creator=creator,
        coin_creator=coin_creator,
        base_mint=base_mint,
        quote_mint=quote_mint,
        lp_mint=lp_mint,
        pool_base_token_account=pool_base_token_account,
        pool_quote_token_account=pool_quote_token_account,
        lp_fee_basis_points=lp_fee_basis_points,
        protocol_fee_basis_points=protocol_fee_basis_points,
        is_pump_amm=is_pump_amm,
        base_is_sol=base_is_sol,
    )


# ---------------------------------------------------------------------------
# Instruction builder
# ---------------------------------------------------------------------------


def build_swap_instruction(
    pool: Pubkey,
    user: Pubkey,
    user_base_token_account: Pubkey,
    user_quote_token_account: Pubkey,
    pool_base_token_account: Pubkey,
    pool_quote_token_account: Pubkey,
    protocol_fee_token_account: Pubkey,
    base_in: bool,
    amount_in: int,
    min_amount_out: int,
    base_token_program: Pubkey = TOKEN_PROGRAM,
) -> Instruction:
    """
    Build the PumpSwap swap instruction.

    Args:
        pool: Pool account address.
        user: Trader's wallet (signer).
        user_base_token_account: User's ATA for the base (meme) token.
        user_quote_token_account: User's ATA for the quote token (WSOL).
        pool_base_token_account: Pool's base token vault.
        pool_quote_token_account: Pool's quote token vault.
        protocol_fee_token_account: Protocol fee recipient's quote ATA.
        base_in: True = sell base for quote, False = buy base with quote.
        amount_in: Input amount (base units / lamports).
        min_amount_out: Minimum output (slippage protection).
        base_token_program: Token program for base token (SPL or Token-2022).

    Returns:
        Solders Instruction ready to add to a transaction.
    """
    data = PUMPSWAP_SWAP_DISCRIMINATOR + struct.pack("<BQQ", int(base_in), amount_in, min_amount_out)

    accounts = [
        AccountMeta(PUMP_SWAP_GLOBAL_CONFIG, is_signer=False, is_writable=False),
        AccountMeta(PUMP_SWAP_FEE_RECIPIENT, is_signer=False, is_writable=True),
        AccountMeta(pool, is_signer=False, is_writable=True),
        AccountMeta(user, is_signer=True, is_writable=True),
        AccountMeta(user_base_token_account, is_signer=False, is_writable=True),
        AccountMeta(user_quote_token_account, is_signer=False, is_writable=True),
        AccountMeta(pool_base_token_account, is_signer=False, is_writable=True),
        AccountMeta(pool_quote_token_account, is_signer=False, is_writable=True),
        AccountMeta(protocol_fee_token_account, is_signer=False, is_writable=True),
        AccountMeta(base_token_program, is_signer=False, is_writable=False),
        AccountMeta(TOKEN_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(PUMP_SWAP_EVENT_AUTHORITY, is_signer=False, is_writable=False),
        AccountMeta(PUMP_SWAP_PROGRAM, is_signer=False, is_writable=False),
    ]

    return Instruction(PUMP_SWAP_PROGRAM, data, accounts)
