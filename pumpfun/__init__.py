"""
pumpfun-python — buy and sell on PumpFun bonding curves + PumpSwap AMM.
Directly from Python. No Jupiter needed.

High-level (read curve → unsigned instructions)::

    import httpx
    from pumpfun import build_buy, build_message, fetch_latest_blockhash
    from solders.transaction import VersionedTransaction

    async with httpx.AsyncClient() as client:
        plan = await build_buy(RPC, wallet.pubkey(), MINT, sol_lamports=100_000_000, http_client=client)
        blockhash = await fetch_latest_blockhash(RPC, http_client=client)
    msg = build_message(wallet.pubkey(), plan.instructions, blockhash)
    tx = VersionedTransaction(msg, [wallet])   # you sign + send

Graduated to an AMM pool? Use the companion package **pumpswap-python**.
"""

from .bonding_curve import (
    BondingCurveState,
    PumpFunError,
    build_buy_instruction,
    build_sell_instruction,
    calculate_buy_amount,
    calculate_sell_amount,
    fetch_bonding_curve_state,
    fetch_fee_recipient,
)
from .constants import (
    PUMP_AMM_PROGRAM,
    PUMP_FUN_PROGRAM,
    PUMP_SWAP_PROGRAM,
)
from .pda import (
    get_associated_token_address,
    get_bonding_curve_pda,
)
from .pumpswap import (
    PoolState,
    build_swap_instruction,
    calculate_swap_output,
    fetch_pool_state,
)
from .rpc import detect_token_program, rpc_call
from .swap import (
    BuyPlan,
    SellPlan,
    build_buy,
    build_close_account,
    build_create_ata_idempotent,
    build_sell,
)
from .tx import build_message, fetch_latest_blockhash, prepend_compute_budget

__version__ = "0.2.0"

__all__ = [
    # High-level (read curve → unsigned instructions)
    "build_buy",
    "build_sell",
    "BuyPlan",
    "SellPlan",
    # Bonding curve (pre-graduation)
    "BondingCurveState",
    "build_buy_instruction",
    "build_sell_instruction",
    "calculate_buy_amount",
    "calculate_sell_amount",
    "fetch_bonding_curve_state",
    "fetch_fee_recipient",
    # PumpSwap AMM (post-graduation) — see also the pumpswap-python package
    "PoolState",
    "build_swap_instruction",
    "calculate_swap_output",
    "fetch_pool_state",
    # SPL + tx helpers
    "build_create_ata_idempotent",
    "build_close_account",
    "build_message",
    "prepend_compute_budget",
    "fetch_latest_blockhash",
    # RPC
    "rpc_call",
    "detect_token_program",
    "PumpFunError",
    # PDA helpers
    "get_associated_token_address",
    "get_bonding_curve_pda",
    # Program IDs
    "PUMP_FUN_PROGRAM",
    "PUMP_SWAP_PROGRAM",
    "PUMP_AMM_PROGRAM",
    "__version__",
]
