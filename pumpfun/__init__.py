"""
pumpfun-python — buy and sell on PumpFun bonding curves + PumpSwap AMM.
Directly from Python. No Jupiter needed.
"""

from .bonding_curve import (
    BondingCurveState,
    build_buy_instruction,
    build_sell_instruction,
    calculate_buy_amount,
    calculate_sell_amount,
    fetch_bonding_curve_state,
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

__version__ = "0.1.0"

__all__ = [
    # Bonding curve (pre-graduation)
    "BondingCurveState",
    "build_buy_instruction",
    "build_sell_instruction",
    "calculate_buy_amount",
    "calculate_sell_amount",
    "fetch_bonding_curve_state",
    # PumpSwap AMM (post-graduation)
    "PoolState",
    "build_swap_instruction",
    "calculate_swap_output",
    "fetch_pool_state",
    # PDA helpers
    "get_associated_token_address",
    "get_bonding_curve_pda",
    # Program IDs
    "PUMP_FUN_PROGRAM",
    "PUMP_SWAP_PROGRAM",
    "PUMP_AMM_PROGRAM",
    "__version__",
]
