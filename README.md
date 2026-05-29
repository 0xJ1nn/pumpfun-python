# pumpfun-python

**Buy and sell on PumpFun bonding curves + PumpSwap AMM. Directly from Python. No Jupiter needed.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Typed](https://img.shields.io/badge/typed-py.typed-blue.svg)](https://peps.python.org/pep-0561/)

---

## Why?

PumpFun tokens start on a **bonding curve** and graduate to a **PumpSwap AMM pool**. Jupiter doesn't always route through these — and when it does, you're at the mercy of their routing engine. This library builds the raw Solana instructions so you can swap directly.

- **Pre-graduation** — buy/sell against the PumpFun bonding curve (v2, 16/14 accounts)
- **One-call helpers** — `build_buy` / `build_sell` read the curve, quote, and return ready unsigned instructions
- **Post-graduation** — legacy PumpSwap swap (13 accounts) + pool readers. For the **current Pump AMM (pAMMBay)** buy/sell path, use the companion package **[pumpswap-python](https://github.com/JinUltimate1995/pumpswap-python)**.
- **Zero dependencies beyond solders + httpx** — no SDK bloat
- **Production-tested** — extracted from a live trading system

---

## Install

```bash
pip install pumpfun-python
```

Or from source:

```bash
pip install git+https://github.com/JinUltimate1995/pumpfun-python.git
```

---

## Quick Start

### 🚀 One-call buy/sell (read curve → unsigned instructions)

```python
import asyncio, httpx
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from pumpfun import build_buy, build_message, fetch_latest_blockhash

RPC = "https://api.mainnet-beta.solana.com"   # use your own (Helius/QuickNode) for real volume
wallet = Keypair()                            # load your real keypair
MINT = "TokenMintAddress..."

async def main():
    async with httpx.AsyncClient() as client:
        plan = await build_buy(RPC, wallet.pubkey(), MINT, sol_lamports=100_000_000,
                               slippage_bps=500, http_client=client)
        blockhash = await fetch_latest_blockhash(RPC, http_client=client)
    print(f"expected_tokens={plan.expected_tokens:,} max_sol_cost={plan.max_sol_cost}")
    msg = build_message(wallet.pubkey(), plan.instructions, blockhash)
    tx = VersionedTransaction(msg, [wallet])  # ← you sign + send

asyncio.run(main())
```

Selling is symmetric: `await build_sell(RPC, wallet.pubkey(), MINT, token_amount=1_000_000, http_client=client)`.

### 💰 Calculate buy/sell amounts (no RPC needed)

```python
from pumpfun import calculate_buy_amount, calculate_sell_amount

# How many tokens for 0.1 SOL?
tokens = calculate_buy_amount(
    sol_amount_lamports=100_000_000,  # 0.1 SOL
    virtual_sol_reserves=30_000_000_000,
    virtual_token_reserves=1_000_000_000_000,
)
print(f"Tokens received: {tokens:,}")

# How much SOL for selling 1M tokens?
sol_out = calculate_sell_amount(
    token_amount=1_000_000,
    virtual_sol_reserves=30_000_000_000,
    virtual_token_reserves=1_000_000_000_000,
)
print(f"SOL received: {sol_out / 1e9:.6f}")
```

### 📈 Read bonding curve state

> **RPC calls require your own Solana RPC endpoint.** Get a free key from [Helius](https://helius.dev), [QuickNode](https://quicknode.com), or use the public endpoint (rate-limited).

```python
import asyncio
from pumpfun import fetch_bonding_curve_state

async def main():
    state = await fetch_bonding_curve_state(
        rpc_url="https://api.mainnet-beta.solana.com",
        token_mint="YourTokenMintAddress",
    )
    print(f"Reserves: {state.virtual_sol_reserves} SOL, {state.virtual_token_reserves} tokens")
    print(f"Complete (graduated): {state.complete}")
    print(f"Creator: {state.creator}")

asyncio.run(main())
```

### 🔨 Build a buy instruction

```python
from solders.pubkey import Pubkey
from pumpfun import build_buy_instruction, get_bonding_curve_pda

user = Pubkey.from_string("YourWalletAddress")
token_mint = Pubkey.from_string("TokenMintAddress")
bonding_curve = get_bonding_curve_pda(token_mint)

ix = build_buy_instruction(
    user=user,
    token_mint=token_mint,
    bonding_curve=bonding_curve,
    sol_amount_lamports=100_000_000,  # 0.1 SOL max
    min_tokens_out=950_000,           # slippage protection
    creator=Pubkey.from_string("CreatorAddress"),
    fee_recipient=Pubkey.from_string("62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV"),
)
# Add `ix` to your transaction
```

### 🏊 PumpSwap AMM swap

```python
from pumpfun import calculate_swap_output, build_swap_instruction, fetch_pool_state

# Read pool state
pool = await fetch_pool_state(rpc_url, "PoolAddress")

# Calculate output
amount_out, fee = calculate_swap_output(
    amount_in=100_000_000,  # 0.1 SOL
    reserve_in=5_000_000_000,
    reserve_out=1_000_000_000_000,
    lp_fee_bps=pool.lp_fee_basis_points,
    protocol_fee_bps=pool.protocol_fee_basis_points,
)
```

---

## API Reference

### High-level (read curve → unsigned instructions)

| Function | Description |
|---|---|
| `build_buy()` | Read curve, quote, return `BuyPlan` (create-ATA + buy) |
| `build_sell()` | Read curve, quote, return `SellPlan` (sell + close-ATA) |
| `build_message()` | Compile a v0 message (compute budget prepended) for signing |
| `fetch_latest_blockhash()` | Recent blockhash for transaction assembly |
| `detect_token_program()` | SPL Token vs Token-2022, auto-detected per mint |

### Bonding Curve (pre-graduation)

| Function | Description |
|---|---|
| `calculate_buy_amount()` | Tokens received for SOL input (1% fee) |
| `calculate_sell_amount()` | SOL received for token input (1% fee) |
| `build_buy_instruction()` | Build PumpFun v2 BUY ix (16 accounts) |
| `build_sell_instruction()` | Build PumpFun v2 SELL ix (14 accounts) |
| `fetch_bonding_curve_state()` | Read reserves, creator, completion from chain |
| `fetch_fee_recipient()` | Read fee recipient from Global account |

### PumpSwap AMM (post-graduation)

| Function | Description |
|---|---|
| `calculate_swap_output()` | Output amount for constant-product swap |
| `build_swap_instruction()` | Build PumpSwap swap ix (13 accounts) |
| `fetch_pool_state()` | Read pool vaults, mints, fees from chain |

### PDA Helpers

| Function | Description |
|---|---|
| `get_bonding_curve_pda()` | Derive bonding curve PDA for a mint |
| `get_associated_token_address()` | Derive ATA (SPL Token or Token-2022) |

### Constants

All program IDs are exported: `PUMP_FUN_PROGRAM`, `PUMP_SWAP_PROGRAM`, `PUMP_AMM_PROGRAM`, plus system programs, discriminators, and fee accounts.

---

## Account Layout Notes

**BUY instruction** uses 16 accounts + 1 remaining account (bonding-curve-v2 PDA).

**SELL instruction** uses 14 accounts + 1 remaining — but **creator_vault [8] and token_program [9] are SWAPPED** relative to buy. This is an undocumented PumpFun quirk that causes failed transactions if you copy the buy layout.

**Pump AMM pools** (pAMMBay program) can have **reversed base/quote** — base_mint=SOL, quote_mint=TOKEN. The `PoolState.base_is_sol` flag indicates this.

---

## Also by JinUltimate1995

- **[pumpswap-python](https://github.com/JinUltimate1995/pumpswap-python)** — direct Pump AMM (pAMMBay) swaps for *graduated* tokens. The natural next step once a curve completes.
- **[jupiter-swap-python](https://github.com/JinUltimate1995/jupiter-swap-python)** — Jupiter swap client for Python. Async. Typed.
- **[solana-rpc-resilient](https://github.com/JinUltimate1995/solana-rpc-resilient)** — Fault-tolerant Solana RPC with automatic failover.
- **[dexscreener-python](https://github.com/JinUltimate1995/dexscreener-python)** — DexScreener API client for Python.

---

## License

MIT
