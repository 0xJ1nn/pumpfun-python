"""
PumpFun bonding curve v2 — buy/sell instructions and on-chain state reading.

Program: 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P

BUY:  16 accounts
SELL: 14 accounts (creator_vault and token_program are SWAPPED vs buy)
"""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass

import httpx
from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey

from .constants import (
    PUMP_BUY_DISCRIMINATOR,
    PUMP_FEE_PROGRAM,
    PUMP_FUN_EVENT_AUTHORITY,
    PUMP_FUN_GLOBAL,
    PUMP_FUN_PROGRAM,
    PUMP_SELL_DISCRIMINATOR,
    SYSTEM_PROGRAM,
    TOKEN_PROGRAM,
)
from .pda import (
    get_associated_token_address,
    get_bonding_curve_pda,
    get_bonding_curve_v2_pda,
    get_creator_vault_pda,
    get_fee_config_pda,
    get_global_volume_accumulator_pda,
    get_user_volume_accumulator_pda,
)


class PumpFunError(Exception):
    """Raised when a PumpFun operation fails."""


@dataclass(slots=True)
class BondingCurveState:
    """Parsed on-chain bonding curve account state."""

    virtual_token_reserves: int
    virtual_sol_reserves: int
    real_token_reserves: int
    real_sol_reserves: int
    token_total_supply: int
    complete: bool
    creator: Pubkey
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False


# ---------------------------------------------------------------------------
# Price calculations (pure functions — no RPC needed)
# ---------------------------------------------------------------------------


def calculate_buy_amount(
    sol_amount_lamports: int,
    virtual_sol_reserves: int,
    virtual_token_reserves: int,
) -> int:
    """
    Calculate tokens received for a given SOL input.

    Uses PumpFun's constant-product formula with 1% fee on SOL input.

    Args:
        sol_amount_lamports: SOL amount in lamports.
        virtual_sol_reserves: Virtual SOL reserves from bonding curve state.
        virtual_token_reserves: Virtual token reserves from bonding curve state.

    Returns:
        Number of tokens received.
    """
    fee = sol_amount_lamports // 100
    sol_after_fee = sol_amount_lamports - fee
    tokens_out = (virtual_token_reserves * sol_after_fee) // (virtual_sol_reserves + sol_after_fee)
    return tokens_out


def calculate_sell_amount(
    token_amount: int,
    virtual_sol_reserves: int,
    virtual_token_reserves: int,
) -> int:
    """
    Calculate SOL received for selling tokens.

    Uses PumpFun's constant-product formula with 1% fee on SOL output.

    Args:
        token_amount: Number of tokens to sell.
        virtual_sol_reserves: Virtual SOL reserves from bonding curve state.
        virtual_token_reserves: Virtual token reserves from bonding curve state.

    Returns:
        SOL output in lamports (after fee).
    """
    if virtual_token_reserves + token_amount == 0:
        return 0
    sol_out_raw = (virtual_sol_reserves * token_amount) // (virtual_token_reserves + token_amount)
    fee = sol_out_raw // 100
    return sol_out_raw - fee


# ---------------------------------------------------------------------------
# On-chain state reading
# ---------------------------------------------------------------------------


async def fetch_bonding_curve_state(
    rpc_url: str,
    token_mint: str | Pubkey,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> BondingCurveState:
    """
    Fetch the PumpFun bonding curve state from on-chain.

    Args:
        rpc_url: Solana RPC endpoint URL.
        token_mint: Token mint address (string or Pubkey).
        http_client: Optional httpx client (creates one if not provided).

    Returns:
        BondingCurveState with reserves, creator, completion status.

    Raises:
        PumpFunError: If the account can't be read or parsed.
    """
    if isinstance(token_mint, str):
        token_mint = Pubkey.from_string(token_mint)

    bonding_curve = get_bonding_curve_pda(token_mint)

    should_close = http_client is None
    client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    try:
        resp = await client.post(rpc_url, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [str(bonding_curve), {"encoding": "base64"}],
        })
        resp.raise_for_status()
        data = resp.json()
    finally:
        if should_close:
            await client.aclose()

    result = data.get("result", {})
    value = result.get("value")
    if not value:
        raise PumpFunError(f"Bonding curve account {bonding_curve} not found")

    raw_data = value.get("data", [])
    if not isinstance(raw_data, list) or not raw_data:
        raise PumpFunError("Cannot decode bonding curve account data")

    account_bytes = base64.b64decode(raw_data[0])

    if len(account_bytes) < 81:
        raise PumpFunError(f"Bonding curve data too short: {len(account_bytes)} bytes")

    # Layout offsets after the 8-byte Anchor discriminator.
    virtual_token_reserves = struct.unpack_from("<Q", account_bytes, 8)[0]
    virtual_sol_reserves = struct.unpack_from("<Q", account_bytes, 16)[0]
    real_token_reserves = struct.unpack_from("<Q", account_bytes, 24)[0]
    real_sol_reserves = struct.unpack_from("<Q", account_bytes, 32)[0]
    token_total_supply = struct.unpack_from("<Q", account_bytes, 40)[0]
    complete = account_bytes[48] != 0
    creator = Pubkey.from_bytes(account_bytes[49:81])

    is_mayhem_mode = len(account_bytes) >= 82 and account_bytes[81] != 0
    is_cashback_coin = len(account_bytes) >= 83 and account_bytes[82] != 0

    return BondingCurveState(
        virtual_token_reserves=virtual_token_reserves,
        virtual_sol_reserves=virtual_sol_reserves,
        real_token_reserves=real_token_reserves,
        real_sol_reserves=real_sol_reserves,
        token_total_supply=token_total_supply,
        complete=complete,
        creator=creator,
        is_mayhem_mode=is_mayhem_mode,
        is_cashback_coin=is_cashback_coin,
    )


async def fetch_fee_recipient(
    rpc_url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> Pubkey:
    """
    Read the fee_recipient from the PumpFun Global account.

    Falls back to default on failure.
    """
    default = Pubkey.from_string("62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV")

    should_close = http_client is None
    client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    try:
        resp = await client.post(rpc_url, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [str(PUMP_FUN_GLOBAL), {"encoding": "base64"}],
        })
        resp.raise_for_status()
        data = resp.json()
        value = data.get("result", {}).get("value")
        if value:
            raw = value.get("data", [])
            if isinstance(raw, list) and raw:
                buf = base64.b64decode(raw[0])
                if len(buf) >= 73:
                    return Pubkey.from_bytes(buf[41:73])
    except Exception:
        pass
    finally:
        if should_close:
            await client.aclose()

    return default


# ---------------------------------------------------------------------------
# Instruction builders (pure functions)
# ---------------------------------------------------------------------------


def build_buy_instruction(
    user: Pubkey,
    token_mint: Pubkey,
    bonding_curve: Pubkey,
    sol_amount_lamports: int,
    min_tokens_out: int,
    creator: Pubkey,
    fee_recipient: Pubkey,
    token_program: Pubkey = TOKEN_PROGRAM,
) -> Instruction:
    """
    Build the PumpFun v2 BUY instruction (16 accounts).

    Args:
        user: Buyer's wallet (signer).
        token_mint: Token mint address.
        bonding_curve: Bonding curve PDA (from get_bonding_curve_pda).
        sol_amount_lamports: Max SOL to spend (lamports).
        min_tokens_out: Minimum tokens expected (slippage protection).
        creator: Token creator from bonding curve state.
        fee_recipient: Fee recipient (from fetch_fee_recipient or default).
        token_program: TOKEN_PROGRAM or TOKEN_2022_PROGRAM.

    Returns:
        Solders Instruction ready to add to a transaction.
    """
    associated_user = get_associated_token_address(user, token_mint, token_program)
    associated_bonding_curve = get_associated_token_address(bonding_curve, token_mint, token_program)
    creator_vault = get_creator_vault_pda(creator)
    global_vol = get_global_volume_accumulator_pda()
    user_vol = get_user_volume_accumulator_pda(user)
    fee_config = get_fee_config_pda()

    data = (
        PUMP_BUY_DISCRIMINATOR
        + struct.pack("<Q", min_tokens_out)
        + struct.pack("<Q", sol_amount_lamports)
        + b"\x01"  # track_volume = Some(true)
    )

    accounts = [
        AccountMeta(PUMP_FUN_GLOBAL, is_signer=False, is_writable=False),
        AccountMeta(fee_recipient, is_signer=False, is_writable=True),
        AccountMeta(token_mint, is_signer=False, is_writable=False),
        AccountMeta(bonding_curve, is_signer=False, is_writable=True),
        AccountMeta(associated_bonding_curve, is_signer=False, is_writable=True),
        AccountMeta(associated_user, is_signer=False, is_writable=True),
        AccountMeta(user, is_signer=True, is_writable=True),
        AccountMeta(SYSTEM_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(token_program, is_signer=False, is_writable=False),
        AccountMeta(creator_vault, is_signer=False, is_writable=True),
        AccountMeta(PUMP_FUN_EVENT_AUTHORITY, is_signer=False, is_writable=False),
        AccountMeta(PUMP_FUN_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(global_vol, is_signer=False, is_writable=True),
        AccountMeta(user_vol, is_signer=False, is_writable=True),
        AccountMeta(fee_config, is_signer=False, is_writable=False),
        AccountMeta(PUMP_FEE_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(get_bonding_curve_v2_pda(token_mint), is_signer=False, is_writable=False),
    ]

    return Instruction(PUMP_FUN_PROGRAM, data, accounts)


def build_sell_instruction(
    user: Pubkey,
    token_mint: Pubkey,
    bonding_curve: Pubkey,
    token_amount: int,
    min_sol_output: int,
    creator: Pubkey,
    fee_recipient: Pubkey,
    token_program: Pubkey = TOKEN_PROGRAM,
) -> Instruction:
    """
    Build the PumpFun v2 SELL instruction (14 accounts).

    NOTE: creator_vault [8] and token_program [9] are SWAPPED vs buy!

    Args:
        user: Seller's wallet (signer).
        token_mint: Token mint address.
        bonding_curve: Bonding curve PDA.
        token_amount: Number of tokens to sell.
        min_sol_output: Minimum SOL output (lamports, slippage protection).
        creator: Token creator from bonding curve state.
        fee_recipient: Fee recipient.
        token_program: TOKEN_PROGRAM or TOKEN_2022_PROGRAM.

    Returns:
        Solders Instruction.
    """
    associated_user = get_associated_token_address(user, token_mint, token_program)
    associated_bonding_curve = get_associated_token_address(bonding_curve, token_mint, token_program)
    creator_vault = get_creator_vault_pda(creator)
    fee_config = get_fee_config_pda()

    data = (
        PUMP_SELL_DISCRIMINATOR
        + struct.pack("<Q", token_amount)
        + struct.pack("<Q", min_sol_output)
    )

    accounts = [
        AccountMeta(PUMP_FUN_GLOBAL, is_signer=False, is_writable=False),
        AccountMeta(fee_recipient, is_signer=False, is_writable=True),
        AccountMeta(token_mint, is_signer=False, is_writable=False),
        AccountMeta(bonding_curve, is_signer=False, is_writable=True),
        AccountMeta(associated_bonding_curve, is_signer=False, is_writable=True),
        AccountMeta(associated_user, is_signer=False, is_writable=True),
        AccountMeta(user, is_signer=True, is_writable=True),
        AccountMeta(SYSTEM_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(creator_vault, is_signer=False, is_writable=True),   # [8] SWAPPED
        AccountMeta(token_program, is_signer=False, is_writable=False),  # [9] SWAPPED
        AccountMeta(PUMP_FUN_EVENT_AUTHORITY, is_signer=False, is_writable=False),
        AccountMeta(PUMP_FUN_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(fee_config, is_signer=False, is_writable=False),
        AccountMeta(PUMP_FEE_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(get_bonding_curve_v2_pda(token_mint), is_signer=False, is_writable=False),
    ]

    return Instruction(PUMP_FUN_PROGRAM, data, accounts)
