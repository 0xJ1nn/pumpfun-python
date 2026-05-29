import base64
import json
import struct

import httpx
import pytest
from solders.pubkey import Pubkey  # type: ignore[import-untyped]

from pumpfun import build_buy, build_sell
from pumpfun.bonding_curve import PumpFunError
from pumpfun.constants import PUMP_BUY_DISCRIMINATOR, PUMP_SELL_DISCRIMINATOR, TOKEN_2022_PROGRAM
from pumpfun.pda import get_bonding_curve_pda

RPC = "http://rpc"
USER = Pubkey.from_bytes(bytes([2]) + bytes(31))
MINT = Pubkey.from_bytes(bytes([20]) + bytes(31))
CREATOR = Pubkey.from_bytes(bytes([40]) + bytes(31))
BONDING_CURVE = str(get_bonding_curve_pda(MINT))


def _curve_bytes(*, complete: bool) -> bytes:
    buf = bytearray(8)  # discriminator
    buf += struct.pack("<Q", 1_000_000_000_000_000)  # virtual_token_reserves
    buf += struct.pack("<Q", 30_000_000_000)         # virtual_sol_reserves
    buf += struct.pack("<Q", 800_000_000_000_000)    # real_token_reserves
    buf += struct.pack("<Q", 0)                       # real_sol_reserves
    buf += struct.pack("<Q", 1_000_000_000_000_000)  # token_total_supply
    buf += bytes([1 if complete else 0])              # complete
    buf += bytes(CREATOR)                             # creator
    return bytes(buf)


def _client(*, complete: bool = False) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method, params = body["method"], body.get("params", [])
        if method == "getAccountInfo":
            addr = params[0]
            if addr == BONDING_CURVE:
                return httpx.Response(200, json={"result": {"value": {
                    "data": [base64.b64encode(_curve_bytes(complete=complete)).decode(), "base64"],
                    "owner": "any",
                }}})
            if addr == str(MINT):
                return httpx.Response(200, json={"result": {"value": {
                    "data": ["", "base64"], "owner": str(TOKEN_2022_PROGRAM),
                }}})
            return httpx.Response(200, json={"result": {"value": None}})
        return httpx.Response(200, json={"result": {}})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_build_buy_returns_create_ata_plus_buy():
    client = _client()
    plan = await build_buy(RPC, USER, MINT, sol_lamports=100_000_000, http_client=client)
    assert plan.expected_tokens > 0
    assert plan.max_sol_cost > plan.sol_in
    assert len(plan.instructions) == 2
    buy_ix = plan.instructions[1]
    assert bytes(buy_ix.data)[:8] == PUMP_BUY_DISCRIMINATOR
    assert len(buy_ix.accounts) == 17  # 16 + bonding-curve-v2 remaining account
    await client.aclose()


@pytest.mark.asyncio
async def test_build_sell_returns_sell_plus_close():
    client = _client()
    plan = await build_sell(RPC, USER, MINT, token_amount=1_000_000_000, http_client=client)
    assert plan.expected_sol_out > 0
    assert plan.min_sol_out <= plan.expected_sol_out
    assert len(plan.instructions) == 2
    sell_ix = plan.instructions[0]
    assert bytes(sell_ix.data)[:8] == PUMP_SELL_DISCRIMINATOR
    assert len(sell_ix.accounts) == 15  # 14 + bonding-curve-v2 remaining account
    await client.aclose()


@pytest.mark.asyncio
async def test_graduated_curve_rejected():
    client = _client(complete=True)
    with pytest.raises(PumpFunError, match="graduated"):
        await build_buy(RPC, USER, MINT, sol_lamports=100_000_000, http_client=client)
    await client.aclose()
