"""Tests for PumpSwap AMM swap calculations and instruction builder."""

from __future__ import annotations

import base64
import struct

import pytest
from solders.pubkey import Pubkey

from pumpfun.constants import (
    PUMP_AMM_PROGRAM,
    PUMP_SWAP_PROGRAM,
    PUMPSWAP_SWAP_DISCRIMINATOR,
    SOL_MINT,
)
from pumpfun.pumpswap import (
    PoolState,
    PumpSwapError,
    build_swap_instruction,
    calculate_swap_output,
    fetch_pool_state,
)


TEST_USER = Pubkey.from_string("11111111111111111111111111111112")
TEST_POOL = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
TEST_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")


# ---------------------------------------------------------------------------
# Swap math
# ---------------------------------------------------------------------------


class TestCalculateSwapOutput:
    def test_basic_swap(self):
        amount_out, fee = calculate_swap_output(
            amount_in=100_000_000,
            reserve_in=5_000_000_000,
            reserve_out=1_000_000_000_000,
            lp_fee_bps=200,
            protocol_fee_bps=100,
        )
        assert amount_out > 0
        assert fee > 0

    def test_fee_deducted_from_input(self):
        """3% total fee (200 + 100 bps) is deducted from input."""
        amount_in = 100_000_000
        _, fee = calculate_swap_output(
            amount_in=amount_in,
            reserve_in=5_000_000_000,
            reserve_out=1_000_000_000_000,
            lp_fee_bps=200,
            protocol_fee_bps=100,
        )
        assert fee == amount_in * 300 // 10_000

    def test_zero_input(self):
        amount_out, fee = calculate_swap_output(0, 5_000_000_000, 1_000_000_000_000, 200, 100)
        assert amount_out == 0
        assert fee == 0

    def test_no_fee(self):
        amount_out_fee, _ = calculate_swap_output(
            100_000_000, 5_000_000_000, 1_000_000_000_000, 200, 100,
        )
        amount_out_no_fee, _ = calculate_swap_output(
            100_000_000, 5_000_000_000, 1_000_000_000_000, 0, 0,
        )
        assert amount_out_no_fee > amount_out_fee

    def test_empty_pool_guard(self):
        amount_out, fee = calculate_swap_output(100_000_000, 0, 1_000_000_000_000, 200, 100)
        assert amount_out > 0  # reserve_in=0 + amount_after_fee > 0, works out

    def test_constant_product_invariant(self):
        """After swap, k = reserve_in * reserve_out should increase (fees retained)."""
        reserve_in = 5_000_000_000
        reserve_out = 1_000_000_000_000
        k_before = reserve_in * reserve_out

        amount_in = 100_000_000
        amount_out, fee = calculate_swap_output(
            amount_in, reserve_in, reserve_out, 200, 100,
        )
        amount_in_after_fee = amount_in - fee
        k_after = (reserve_in + amount_in_after_fee) * (reserve_out - amount_out)
        assert k_after >= k_before


# ---------------------------------------------------------------------------
# Instruction builder
# ---------------------------------------------------------------------------


class TestBuildSwapInstruction:
    def _build_ix(self, base_in: bool = True):
        return build_swap_instruction(
            pool=TEST_POOL,
            user=TEST_USER,
            user_base_token_account=Pubkey.default(),
            user_quote_token_account=Pubkey.default(),
            pool_base_token_account=Pubkey.default(),
            pool_quote_token_account=Pubkey.default(),
            protocol_fee_token_account=Pubkey.default(),
            base_in=base_in,
            amount_in=100_000_000,
            min_amount_out=50_000,
        )

    def test_accounts_count(self):
        ix = self._build_ix()
        assert len(ix.accounts) == 13

    def test_program_id(self):
        ix = self._build_ix()
        assert ix.program_id == PUMP_SWAP_PROGRAM

    def test_data_format(self):
        ix = self._build_ix(base_in=True)
        data = bytes(ix.data)
        assert data[:8] == PUMPSWAP_SWAP_DISCRIMINATOR
        base_in_flag = data[8]
        amount_in = struct.unpack_from("<Q", data, 9)[0]
        min_out = struct.unpack_from("<Q", data, 17)[0]
        assert base_in_flag == 1
        assert amount_in == 100_000_000
        assert min_out == 50_000

    def test_buy_direction(self):
        ix = self._build_ix(base_in=False)
        data = bytes(ix.data)
        assert data[8] == 0  # base_in = False = buy

    def test_user_is_signer(self):
        ix = self._build_ix()
        assert ix.accounts[3].pubkey == TEST_USER
        assert ix.accounts[3].is_signer


# ---------------------------------------------------------------------------
# Pool state parsing (mocked)
# ---------------------------------------------------------------------------


def _make_pool_data(
    pool_bump: int = 254,
    index: int = 42,
    creator: Pubkey | None = None,
    base_mint: Pubkey | None = None,
    quote_mint: Pubkey | None = None,
    lp_fee_bps: int = 200,
    proto_fee_bps: int = 100,
    owner: str | None = None,
) -> tuple[bytes, str]:
    """Build fake pool account data + owner string."""
    creator = creator or TEST_USER
    base_mint = base_mint or TEST_MINT
    quote_mint = quote_mint or SOL_MINT
    lp_mint = Pubkey.default()
    base_vault = Pubkey.default()
    quote_vault = Pubkey.default()
    owner = owner or str(PUMP_SWAP_PROGRAM)

    buf = b"\x00" * 8  # discriminator
    buf += bytes([pool_bump])
    buf += struct.pack("<H", index)
    buf += bytes(creator)
    buf += bytes(base_mint)
    buf += bytes(quote_mint)
    buf += bytes(lp_mint)
    buf += bytes(base_vault)
    buf += bytes(quote_vault)
    buf += struct.pack("<Q", lp_fee_bps)
    buf += struct.pack("<Q", proto_fee_bps)
    return buf, owner


class TestFetchPoolState:
    @pytest.mark.asyncio
    async def test_parse_legacy_pool(self, httpx_mock):
        buf, owner = _make_pool_data()
        encoded = base64.b64encode(buf).decode()

        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "data": [encoded, "base64"],
                    "owner": owner,
                }
            }
        })

        state = await fetch_pool_state("https://rpc.example.com", "SomePoolAddress")
        assert isinstance(state, PoolState)
        assert state.lp_fee_basis_points == 200
        assert state.protocol_fee_basis_points == 100
        assert not state.is_pump_amm
        assert not state.base_is_sol

    @pytest.mark.asyncio
    async def test_parse_pump_amm_pool(self, httpx_mock):
        buf, _ = _make_pool_data(owner=str(PUMP_AMM_PROGRAM))
        # For Pump AMM, extend buffer for coin_creator field (lp_supply u64 + coin_creator Pubkey)
        buf += struct.pack("<Q", 0)  # lp_supply
        buf += bytes(TEST_USER)  # coin_creator
        encoded = base64.b64encode(buf).decode()

        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "data": [encoded, "base64"],
                    "owner": str(PUMP_AMM_PROGRAM),
                }
            }
        })

        state = await fetch_pool_state("https://rpc.example.com", "SomePoolAddress")
        assert state.is_pump_amm
        assert state.lp_fee_basis_points == 200  # default
        assert state.protocol_fee_basis_points == 100  # default

    @pytest.mark.asyncio
    async def test_not_found_raises(self, httpx_mock):
        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"value": None}
        })

        with pytest.raises(PumpSwapError, match="not found"):
            await fetch_pool_state("https://rpc.example.com", "BadPool")

    @pytest.mark.asyncio
    async def test_wrong_owner_raises(self, httpx_mock):
        buf, _ = _make_pool_data()
        encoded = base64.b64encode(buf).decode()

        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "data": [encoded, "base64"],
                    "owner": "SomeRandomProgram111111111111111111111",
                }
            }
        })

        with pytest.raises(PumpSwapError, match="not PumpSwap"):
            await fetch_pool_state("https://rpc.example.com", "BadOwnerPool")

    @pytest.mark.asyncio
    async def test_too_short_raises(self, httpx_mock):
        short_data = base64.b64encode(b"\x00" * 50).decode()
        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "data": [short_data, "base64"],
                    "owner": str(PUMP_SWAP_PROGRAM),
                }
            }
        })

        with pytest.raises(PumpSwapError, match="too short"):
            await fetch_pool_state("https://rpc.example.com", "ShortPool")

    @pytest.mark.asyncio
    async def test_base_is_sol_flag(self, httpx_mock):
        """Pump AMM pools can have reversed base/quote (base=SOL)."""
        buf, _ = _make_pool_data(
            base_mint=SOL_MINT,
            quote_mint=TEST_MINT,
            owner=str(PUMP_AMM_PROGRAM),
        )
        # Extend for coin_creator
        buf += struct.pack("<Q", 0)  # lp_supply
        buf += bytes(Pubkey.default())  # coin_creator
        encoded = base64.b64encode(buf).decode()

        httpx_mock.add_response(json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "data": [encoded, "base64"],
                    "owner": str(PUMP_AMM_PROGRAM),
                }
            }
        })

        state = await fetch_pool_state("https://rpc.example.com", "ReversedPool")
        assert state.base_is_sol
        assert state.is_pump_amm
