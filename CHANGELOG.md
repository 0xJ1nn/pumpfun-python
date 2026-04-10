# Changelog

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
