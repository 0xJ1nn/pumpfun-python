"""Tests for PDA derivation helpers."""

from solders.pubkey import Pubkey

from pumpfun.constants import PUMP_FEE_PROGRAM, PUMP_FUN_PROGRAM
from pumpfun.pda import (
    get_associated_token_address,
    get_bonding_curve_pda,
    get_bonding_curve_v2_pda,
    get_creator_vault_pda,
    get_fee_config_pda,
    get_global_volume_accumulator_pda,
    get_user_volume_accumulator_pda,
)

# Use a deterministic mint for reproducible tests
TEST_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")  # USDC
TEST_USER = Pubkey.from_string("11111111111111111111111111111112")


class TestBondingCurvePDA:
    def test_deterministic(self):
        pda1 = get_bonding_curve_pda(TEST_MINT)
        pda2 = get_bonding_curve_pda(TEST_MINT)
        assert pda1 == pda2

    def test_different_mints_different_pdas(self):
        mint2 = Pubkey.from_string("So11111111111111111111111111111111111111112")
        pda1 = get_bonding_curve_pda(TEST_MINT)
        pda2 = get_bonding_curve_pda(mint2)
        assert pda1 != pda2

    def test_returns_pubkey(self):
        pda = get_bonding_curve_pda(TEST_MINT)
        assert isinstance(pda, Pubkey)


class TestBondingCurveV2PDA:
    def test_deterministic(self):
        pda1 = get_bonding_curve_v2_pda(TEST_MINT)
        pda2 = get_bonding_curve_v2_pda(TEST_MINT)
        assert pda1 == pda2

    def test_different_from_v1(self):
        v1 = get_bonding_curve_pda(TEST_MINT)
        v2 = get_bonding_curve_v2_pda(TEST_MINT)
        assert v1 != v2


class TestCreatorVaultPDA:
    def test_deterministic(self):
        pda1 = get_creator_vault_pda(TEST_USER)
        pda2 = get_creator_vault_pda(TEST_USER)
        assert pda1 == pda2


class TestAssociatedTokenAddress:
    def test_deterministic(self):
        ata1 = get_associated_token_address(TEST_USER, TEST_MINT)
        ata2 = get_associated_token_address(TEST_USER, TEST_MINT)
        assert ata1 == ata2

    def test_different_owners_different_atas(self):
        user2 = Pubkey.from_string("So11111111111111111111111111111111111111112")
        ata1 = get_associated_token_address(TEST_USER, TEST_MINT)
        ata2 = get_associated_token_address(user2, TEST_MINT)
        assert ata1 != ata2


class TestVolumeAccumulatorPDAs:
    def test_global_deterministic(self):
        pda1 = get_global_volume_accumulator_pda()
        pda2 = get_global_volume_accumulator_pda()
        assert pda1 == pda2

    def test_user_deterministic(self):
        pda1 = get_user_volume_accumulator_pda(TEST_USER)
        pda2 = get_user_volume_accumulator_pda(TEST_USER)
        assert pda1 == pda2

    def test_user_different_from_global(self):
        g = get_global_volume_accumulator_pda()
        u = get_user_volume_accumulator_pda(TEST_USER)
        assert g != u


class TestFeeConfigPDA:
    def test_deterministic(self):
        pda1 = get_fee_config_pda()
        pda2 = get_fee_config_pda()
        assert pda1 == pda2
