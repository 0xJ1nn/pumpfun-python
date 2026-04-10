"""Tests for bonding curve calculations and instruction builders."""

from __future__ import annotations

import struct

import pytest
from solders.pubkey import Pubkey

from pumpfun.bonding_curve import (
    BondingCurveState,
    PumpFunError,
    build_buy_instruction,
    build_sell_instruction,
    calculate_buy_amount,
    calculate_sell_amount,
    fetch_bonding_curve_state,
    fetch_fee_recipient,
)
from pumpfun.constants import (
    PUMP_BUY_DISCRIMINATOR,
    PUMP_FUN_PROGRAM,
    PUMP_SELL_DISCRIMINATOR,
    TOKEN_PROGRAM,
)
from pumpfun.pda import get_bonding_curve_pda


TEST_USER = Pubkey.from_string("11111111111111111111111111111112")
TEST_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
TEST_CREATOR = Pubkey.from_string("So11111111111111111111111111111111111111112")
TEST_FEE_RECIPIENT = Pubkey.from_string("62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV")


# ---------------------------------------------------------------------------
# Price calculations
# ---------------------------------------------------------------------------


class TestCalculateBuyAmount:
    def test_basic_buy(self):
        tokens = calculate_buy_amount(
            sol_amount_lamports=100_000_000,
            virtual_sol_reserves=30_000_000_000,
            virtual_token_reserves=1_000_000_000_000,
        )
        assert tokens > 0

    def test_one_percent_fee(self):
        """1% fee means 100M input uses 99M for the swap."""
        tokens = calculate_buy_amount(100_000_000, 30_000_000_000, 1_000_000_000_000)
        # Manual: fee = 100M // 100 = 1M, effective = 99M
        # tokens = (1T * 99M) / (30B + 99M) = 99_000_000_000_000_000 / 30_099_000_000
        expected = (1_000_000_000_000 * 99_000_000) // (30_000_000_000 + 99_000_000)
        assert tokens == expected

    def test_zero_input(self):
        tokens = calculate_buy_amount(0, 30_000_000_000, 1_000_000_000_000)
        assert tokens == 0

    def test_larger_buy_more_slippage(self):
        """Larger buys get proportionally fewer tokens (bonding curve)."""
        tokens_small = calculate_buy_amount(10_000_000, 30_000_000_000, 1_000_000_000_000)
        tokens_large = calculate_buy_amount(100_000_000, 30_000_000_000, 1_000_000_000_000)
        ratio = tokens_large / tokens_small
        assert ratio < 10  # less than 10x tokens for 10x SOL


class TestCalculateSellAmount:
    def test_basic_sell(self):
        sol_out = calculate_sell_amount(1_000_000, 30_000_000_000, 1_000_000_000_000)
        assert sol_out > 0

    def test_one_percent_fee_on_output(self):
        """Fee reduces SOL output by 1%."""
        sol_out = calculate_sell_amount(1_000_000, 30_000_000_000, 1_000_000_000_000)
        # Without fee it would be = (30B * 1M) / (1T + 1M) ≈ 29_970
        raw = (30_000_000_000 * 1_000_000) // (1_000_000_000_000 + 1_000_000)
        expected = raw - raw // 100
        assert sol_out == expected

    def test_zero_tokens(self):
        sol_out = calculate_sell_amount(0, 30_000_000_000, 1_000_000_000_000)
        assert sol_out == 0

    def test_division_by_zero_guard(self):
        sol_out = calculate_sell_amount(0, 30_000_000_000, 0)
        assert sol_out == 0


# ---------------------------------------------------------------------------
# Instruction builders
# ---------------------------------------------------------------------------


class TestBuildBuyInstruction:
    def test_accounts_count(self):
        ix = build_buy_instruction(
            user=TEST_USER,
            token_mint=TEST_MINT,
            bonding_curve=get_bonding_curve_pda(TEST_MINT),
            sol_amount_lamports=100_000_000,
            min_tokens_out=1_000_000,
            creator=TEST_CREATOR,
            fee_recipient=TEST_FEE_RECIPIENT,
        )
        assert len(ix.accounts) == 17  # 16 accounts + 1 remaining (v2 PDA)

    def test_program_id(self):
        ix = build_buy_instruction(
            user=TEST_USER,
            token_mint=TEST_MINT,
            bonding_curve=get_bonding_curve_pda(TEST_MINT),
            sol_amount_lamports=100_000_000,
            min_tokens_out=1_000_000,
            creator=TEST_CREATOR,
            fee_recipient=TEST_FEE_RECIPIENT,
        )
        assert ix.program_id == PUMP_FUN_PROGRAM

    def test_data_format(self):
        ix = build_buy_instruction(
            user=TEST_USER,
            token_mint=TEST_MINT,
            bonding_curve=get_bonding_curve_pda(TEST_MINT),
            sol_amount_lamports=100_000_000,
            min_tokens_out=1_000_000,
            creator=TEST_CREATOR,
            fee_recipient=TEST_FEE_RECIPIENT,
        )
        data = bytes(ix.data)
        assert data[:8] == PUMP_BUY_DISCRIMINATOR
        min_tokens = struct.unpack_from("<Q", data, 8)[0]
        sol_amount = struct.unpack_from("<Q", data, 16)[0]
        assert min_tokens == 1_000_000
        assert sol_amount == 100_000_000
        assert data[24] == 0x01  # track_volume

    def test_user_is_signer(self):
        ix = build_buy_instruction(
            user=TEST_USER,
            token_mint=TEST_MINT,
            bonding_curve=get_bonding_curve_pda(TEST_MINT),
            sol_amount_lamports=100_000_000,
            min_tokens_out=1_000_000,
            creator=TEST_CREATOR,
            fee_recipient=TEST_FEE_RECIPIENT,
        )
        # Account [6] is user — must be signer + writable
        user_meta = ix.accounts[6]
        assert user_meta.pubkey == TEST_USER
        assert user_meta.is_signer
        assert user_meta.is_writable


class TestBuildSellInstruction:
    def test_accounts_count(self):
        ix = build_sell_instruction(
            user=TEST_USER,
            token_mint=TEST_MINT,
            bonding_curve=get_bonding_curve_pda(TEST_MINT),
            token_amount=1_000_000,
            min_sol_output=50_000,
            creator=TEST_CREATOR,
            fee_recipient=TEST_FEE_RECIPIENT,
        )
        assert len(ix.accounts) == 15  # 14 accounts + 1 remaining (v2 PDA)

    def test_data_format(self):
        ix = build_sell_instruction(
            user=TEST_USER,
            token_mint=TEST_MINT,
            bonding_curve=get_bonding_curve_pda(TEST_MINT),
            token_amount=1_000_000,
            min_sol_output=50_000,
            creator=TEST_CREATOR,
            fee_recipient=TEST_FEE_RECIPIENT,
        )
        data = bytes(ix.data)
        assert data[:8] == PUMP_SELL_DISCRIMINATOR
        token_amount = struct.unpack_from("<Q", data, 8)[0]
        min_sol = struct.unpack_from("<Q", data, 16)[0]
        assert token_amount == 1_000_000
        assert min_sol == 50_000

    def test_creator_vault_before_token_program(self):
        """The SELL instruction SWAPS creator_vault [8] and token_program [9]."""
        ix = build_sell_instruction(
            user=TEST_USER,
            token_mint=TEST_MINT,
            bonding_curve=get_bonding_curve_pda(TEST_MINT),
            token_amount=1_000_000,
            min_sol_output=50_000,
            creator=TEST_CREATOR,
            fee_recipient=TEST_FEE_RECIPIENT,
        )
        # [8] = creator_vault (writable), [9] = token_program (not writable)
        assert ix.accounts[8].is_writable  # creator_vault
        assert not ix.accounts[9].is_writable  # token_program
        assert ix.accounts[9].pubkey == TOKEN_PROGRAM


# ---------------------------------------------------------------------------
# On-chain readers (mocked)
# ---------------------------------------------------------------------------


def _make_bonding_curve_data(
    virtual_token_reserves: int = 1_000_000_000_000,
    virtual_sol_reserves: int = 30_000_000_000,
    real_token_reserves: int = 500_000_000_000,
    real_sol_reserves: int = 15_000_000_000,
    token_total_supply: int = 1_000_000_000_000_000,
    complete: bool = False,
    creator: Pubkey | None = None,
) -> bytes:
    """Build a fake bonding curve account blob."""
    import base64
    creator = creator or TEST_CREATOR
    buf = b"\x00" * 8  # discriminator
    buf += struct.pack("<Q", virtual_token_reserves)
    buf += struct.pack("<Q", virtual_sol_reserves)
    buf += struct.pack("<Q", real_token_reserves)
    buf += struct.pack("<Q", real_sol_reserves)
    buf += struct.pack("<Q", token_total_supply)
    buf += bytes([int(complete)])
    buf += bytes(creator)
    buf += b"\x00\x00"  # mayhem + cashback
    return buf


class TestFetchBondingCurveState:
    @pytest.mark.asyncio
    async def test_parse_state(self, httpx_mock):
        import base64
        raw_data = _make_bonding_curve_data()
        encoded = base64.b64encode(raw_data).decode()

        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "data": [encoded, "base64"],
                    "owner": str(PUMP_FUN_PROGRAM),
                }
            }
        })

        state = await fetch_bonding_curve_state("https://rpc.example.com", TEST_MINT)
        assert isinstance(state, BondingCurveState)
        assert state.virtual_token_reserves == 1_000_000_000_000
        assert state.virtual_sol_reserves == 30_000_000_000
        assert not state.complete
        assert state.creator == TEST_CREATOR

    @pytest.mark.asyncio
    async def test_not_found_raises(self, httpx_mock):
        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"value": None}
        })

        with pytest.raises(PumpFunError, match="not found"):
            await fetch_bonding_curve_state("https://rpc.example.com", TEST_MINT)

    @pytest.mark.asyncio
    async def test_too_short_raises(self, httpx_mock):
        import base64
        short_data = base64.b64encode(b"\x00" * 20).decode()
        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "data": [short_data, "base64"],
                    "owner": str(PUMP_FUN_PROGRAM),
                }
            }
        })

        with pytest.raises(PumpFunError, match="too short"):
            await fetch_bonding_curve_state("https://rpc.example.com", TEST_MINT)


class TestFetchFeeRecipient:
    @pytest.mark.asyncio
    async def test_default_on_failure(self, httpx_mock):
        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"value": None}
        })

        fee = await fetch_fee_recipient("https://rpc.example.com")
        assert str(fee) == "62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV"
