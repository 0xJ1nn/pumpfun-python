"""
Solana program IDs and instruction discriminators for PumpFun and PumpSwap.
"""

import hashlib

from solders.pubkey import Pubkey

# ── PumpFun bonding curve program ──────────────────────────────────────────
PUMP_FUN_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
PUMP_FUN_GLOBAL = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
PUMP_FUN_EVENT_AUTHORITY = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")

# ── PumpSwap AMM — legacy program ─────────────────────────────────────────
PUMP_SWAP_PROGRAM = Pubkey.from_string("PSwapMdSai8tjrEXcxFeQth87xC4rRsa4VA5mhGhXkP")

# ── Pump AMM — current production program (pAMMBay) ───────────────────────
PUMP_AMM_PROGRAM = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA")
PUMP_AMM_GLOBAL_CONFIG = Pubkey.from_string("ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw")
PUMP_AMM_EVENT_AUTHORITY = Pubkey.from_string("GS4CU59F31iL7aR2Q8zVS8DRrcRnXX1yjQ66TqNVQnaR")

# ── Pump Fee program ──────────────────────────────────────────────────────
PUMP_FEE_PROGRAM = Pubkey.from_string("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ")

# ── PumpSwap fee accounts ─────────────────────────────────────────────────
PUMP_SWAP_GLOBAL_CONFIG = Pubkey.from_string("ADyA8hdefbpth3kCbkbEVuNyGPfbmSYdoMjMCuKLxMJo")
PUMP_SWAP_FEE_RECIPIENT = Pubkey.from_string("62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV")
PUMP_SWAP_EVENT_AUTHORITY = Pubkey.from_string("GS4CU59F31iL7aR2Q8xmZRbmMfXdK4cqeLGSBDmkXSWm")

# ── System / Token Programs ───────────────────────────────────────────────
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN_2022_PROGRAM = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
ASSOCIATED_TOKEN_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
SOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")

LAMPORTS_PER_SOL = 1_000_000_000

# ── Instruction discriminators ─────────────────────────────────────────────
# Anchor convention: sha256("global:<instruction_name>")[:8]
PUMP_BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
PUMP_SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
PUMPSWAP_SWAP_DISCRIMINATOR = hashlib.sha256(b"global:swap").digest()[:8]
