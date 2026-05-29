# Changelog

## 0.2.0 (2026-05-29)

### Added
- High-level `build_buy` / `build_sell` — read the bonding curve, quote the trade,
  and return ordered **unsigned** instructions (`BuyPlan` / `SellPlan`).
- `detect_token_program` — SPL Token vs Token-2022 auto-detection per mint.
- `build_create_ata_idempotent` / `build_close_account` SPL helpers.
- Transaction assembly: `build_message` (v0, compute budget prepended),
  `prepend_compute_budget`, `fetch_latest_blockhash`.
- `rpc_call` minimal JSON-RPC helper.
- Exported `fetch_fee_recipient` and `PumpFunError`.

### Changed
- mypy: solders typing handled via config override (no more inline ignores).
- PyPI releases now publish via GitHub Actions Trusted Publishing on a version tag.

### Note
- For the current **Pump AMM (pAMMBay)** buy/sell path on graduated tokens, see the
  companion package [pumpswap-python](https://github.com/JinUltimate1995/pumpswap-python).

## 0.1.0 (2025-07-10)

### Added
- PumpFun bonding curve v2 buy/sell instruction builders (16/14 accounts)
- PumpSwap AMM constant-product swap instruction builder (13 accounts)
- On-chain bonding curve state reader with full field parsing
- PumpSwap pool state reader (legacy + Pump AMM layouts)
- Price calculation helpers — `calculate_buy_amount`, `calculate_sell_amount`, `calculate_swap_output`
- PDA derivation — bonding curve, creator vault, volume accumulators, fee config, ATA
- All program IDs and discriminators for PumpFun, PumpSwap, and Pump AMM
- Full type hints with py.typed marker
