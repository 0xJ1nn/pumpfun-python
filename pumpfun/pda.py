"""
PDA derivation helpers for PumpFun and PumpSwap.
"""

from __future__ import annotations

from solders.pubkey import Pubkey

from .constants import (
    ASSOCIATED_TOKEN_PROGRAM,
    PUMP_FEE_PROGRAM,
    PUMP_FUN_PROGRAM,
    TOKEN_PROGRAM,
)


def _find_pda(seeds: list[bytes], program_id: Pubkey) -> Pubkey:
    """Derive a Program Derived Address."""
    pubkey, _bump = Pubkey.find_program_address(seeds, program_id)
    return pubkey


def get_bonding_curve_pda(token_mint: Pubkey) -> Pubkey:
    """Derive the PumpFun bonding curve PDA for a token mint."""
    return _find_pda([b"bonding-curve", bytes(token_mint)], PUMP_FUN_PROGRAM)


def get_associated_token_address(
    owner: Pubkey,
    mint: Pubkey,
    token_program: Pubkey = TOKEN_PROGRAM,
) -> Pubkey:
    """Derive the Associated Token Account (ATA) address."""
    return _find_pda(
        [bytes(owner), bytes(token_program), bytes(mint)],
        ASSOCIATED_TOKEN_PROGRAM,
    )


def get_creator_vault_pda(creator: Pubkey) -> Pubkey:
    """PDA["creator-vault", creator] on the PumpFun program."""
    return _find_pda([b"creator-vault", bytes(creator)], PUMP_FUN_PROGRAM)


def get_bonding_curve_v2_pda(token_mint: Pubkey) -> Pubkey:
    """PDA["bonding-curve-v2", mint] — required remaining account for v2."""
    return _find_pda([b"bonding-curve-v2", bytes(token_mint)], PUMP_FUN_PROGRAM)


def get_global_volume_accumulator_pda() -> Pubkey:
    """PDA["global_volume_accumulator"] on the PumpFun program."""
    return _find_pda([b"global_volume_accumulator"], PUMP_FUN_PROGRAM)


def get_user_volume_accumulator_pda(user: Pubkey) -> Pubkey:
    """PDA["user_volume_accumulator", user] on the PumpFun program."""
    return _find_pda([b"user_volume_accumulator", bytes(user)], PUMP_FUN_PROGRAM)


def get_fee_config_pda() -> Pubkey:
    """PDA["fee_config", pump_program] on the fee program."""
    return _find_pda(
        [b"fee_config", bytes(PUMP_FUN_PROGRAM)],
        PUMP_FEE_PROGRAM,
    )
