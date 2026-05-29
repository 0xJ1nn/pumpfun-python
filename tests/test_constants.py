"""Tests for constants module."""

import hashlib


from pumpfun.constants import (
    PUMP_AMM_PROGRAM,
    PUMP_BUY_DISCRIMINATOR,
    PUMP_FUN_PROGRAM,
    PUMP_SELL_DISCRIMINATOR,
    PUMP_SWAP_PROGRAM,
    PUMPSWAP_SWAP_DISCRIMINATOR,
    SOL_MINT,
    TOKEN_2022_PROGRAM,
    TOKEN_PROGRAM,
)


class TestProgramIDs:
    def test_pump_fun_program(self):
        assert str(PUMP_FUN_PROGRAM) == "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

    def test_pump_swap_program(self):
        assert str(PUMP_SWAP_PROGRAM) == "PSwapMdSai8tjrEXcxFeQth87xC4rRsa4VA5mhGhXkP"

    def test_pump_amm_program(self):
        assert str(PUMP_AMM_PROGRAM) == "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"

    def test_token_program(self):
        assert str(TOKEN_PROGRAM) == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

    def test_token_2022(self):
        assert str(TOKEN_2022_PROGRAM) == "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

    def test_sol_mint(self):
        assert str(SOL_MINT) == "So11111111111111111111111111111111111111112"


class TestDiscriminators:
    def test_buy_discriminator_length(self):
        assert len(PUMP_BUY_DISCRIMINATOR) == 8

    def test_sell_discriminator_length(self):
        assert len(PUMP_SELL_DISCRIMINATOR) == 8

    def test_swap_discriminator_is_sha256(self):
        expected = hashlib.sha256(b"global:swap").digest()[:8]
        assert PUMPSWAP_SWAP_DISCRIMINATOR == expected

    def test_buy_sell_different(self):
        assert PUMP_BUY_DISCRIMINATOR != PUMP_SELL_DISCRIMINATOR
