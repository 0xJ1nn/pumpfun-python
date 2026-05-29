from solders.hash import Hash  # type: ignore[import-untyped]
from solders.instruction import Instruction  # type: ignore[import-untyped]
from solders.pubkey import Pubkey  # type: ignore[import-untyped]

from pumpfun.constants import SYSTEM_PROGRAM
from pumpfun.tx import build_message, prepend_compute_budget


def _dummy_ix() -> Instruction:
    return Instruction(SYSTEM_PROGRAM, bytes([0]), [])


def test_prepend_compute_budget_adds_two_instructions():
    out = prepend_compute_budget([_dummy_ix()], compute_units=100_000, compute_unit_price=500)
    assert len(out) == 3


def test_build_message_compiles_v0():
    payer = Pubkey.from_bytes(bytes([1]) + bytes(31))
    blockhash = Hash.from_string(str(Pubkey.default()))
    msg = build_message(payer, [_dummy_ix()], blockhash)
    assert len(msg.account_keys) >= 3
    assert msg.recent_blockhash == blockhash
