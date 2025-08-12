import asyncio
import aiohttp
import os

DEBUG = str(os.getenv("DEBUG", "0")).lower() in {"1", "true", "yes"}

def _log(msg: str):
    if DEBUG:
        print(msg)

def _chain_to_openocean(chain_id: int) -> str:
    return {137: "polygon", 42161: "arbitrum", 56: "bsc"}.get(chain_id, "polygon")

async def _fetch_json(session: aiohttp.ClientSession, method: str, url: str, name: str, **kwargs):
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with session.request(method, url, timeout=timeout, **kwargs) as resp:
            if resp.status != 200:
                _log(f"[{name}] HTTP {resp.status} -> {url}")
                return None
            ct = resp.headers.get("content-type","")
            if "application/json" not in ct and "json" not in ct:
                _log(f"[{name}] Unexpected content-type: {ct}")
            return await resp.json()
    except Exception as e:
        _log(f"[{name}] Exception: {e.__class__.__name__}: {e}")
        return None

async def _quote_1inch(session, chain_id, from_token, to_token, amount):
    name = "1inch"
    url = f"https://api.1inch.io/v4.0/{chain_id}/quote"
    params = {
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "amount": str(amount),
    }
    data = await _fetch_json(session, "GET", url, name, params=params)
    if not data:
        return None
    val = data.get("toTokenAmount")
    if not val:
        _log(f"[{name}] missing toTokenAmount")
        return None
    _log(f"[{name}] toAmount={val}")
    return int(val)

async def _quote_0x(session, chain_id, from_token, to_token, amount):
    name = "0x"
    base = "https://polygon.api.0x.org" if chain_id == 137 else "https://api.0x.org"
    url = f"{base}/swap/v1/quote"
    params = {"sellToken": from_token, "buyToken": to_token, "sellAmount": str(amount), "skipValidation": "true"}
    data = await _fetch_json(session, "GET", url, name, params=params)
    if not data:
        return None
    val = data.get("buyAmount")
    if not val:
        _log(f"[{name}] missing buyAmount")
        return None
    _log(f"[{name}] toAmount={val}")
    return int(val)

async def _quote_kyber(session, chain_id, from_token, to_token, amount):
    name = "KyberSwap"
    url = f"https://aggregator-api.kyberswap.com/{chain_id}/route/encode"
    params = {"tokenIn": from_token, "tokenOut": to_token, "amountIn": str(amount), "saveGas": "1", "chainId": str(chain_id)}
    data = await _fetch_json(session, "GET", url, name, params=params)
    if not data:
        return None
    val = data.get("amountOut")
    if not val:
        _log(f"[{name}] missing amountOut")
        return None
    _log(f"[{name}] toAmount={val}")
    return int(val)

async def _quote_openocean(session, chain_id, from_token, to_token, amount):
    name = "OpenOcean"
    chain = _chain_to_openocean(chain_id)
    url = f"https://open-api.openocean.finance/v3/{chain}/quote"
    params = {"inTokenAddress": from_token, "outTokenAddress": to_token, "amount": str(amount)}
    data = await _fetch_json(session, "GET", url, name, params=params)
    if not data:
        return None
    try:
        val = data.get("data", {}).get("outAmount")
    except Exception:
        val = None
    if not val:
        _log(f"[{name}] missing data.outAmount")
        return None
    _log(f"[{name}] toAmount={val}")
    return int(val)

async def _quote_odos(session, chain_id, from_token, to_token, amount):
    name = "Odos"
    url = "https://api.odos.xyz/sor/quote"
    payload = {
        "chainId": int(chain_id),
        "inputTokens": [{"tokenAddress": from_token, "amount": str(amount)}],
        "outputTokens": [{"tokenAddress": to_token, "proportion": 1}],
        "slippageLimitPercent": 0.5,
    }
    data = await _fetch_json(session, "POST", url, name, json=payload)
    if not data:
        return None
    val = data.get("outAmount")
    if val is None:
        out_amounts = data.get("outAmounts")
        if isinstance(out_amounts, list) and out_amounts:
            val = out_amounts[0]
    if val is None:
        _log(f"[{name}] missing outAmount(s)")
        return None
    _log(f"[{name}] toAmount={val}")
    return int(val)

async def get_best_quote_async(session, from_token: str, to_token: str, amount: int, chain_id: int = 137):
    tasks = {
        "1inch": _quote_1inch(session, chain_id, from_token, to_token, amount),
        "0x": _quote_0x(session, chain_id, from_token, to_token, amount),
        "KyberSwap": _quote_kyber(session, chain_id, from_token, to_token, amount),
        "OpenOcean": _quote_openocean(session, chain_id, from_token, to_token, amount),
        "Odos": _quote_odos(session, chain_id, from_token, to_token, amount),
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    best_name, best_val = None, None
    for (name, _), val in zip(tasks.items(), results):
        if isinstance(val, Exception):
            _log(f"[{name}] gather exception: {val}")
            continue
        if val is None:
            _log(f"[{name}] no quote")
            continue
        if best_val is None or val > best_val:
            best_name, best_val = name, val

    if best_name is None:
        _log("[get_best_quote_async] all aggregators failed")
        return None
    _log(f"[get_best_quote_async] best={best_name} toAmount={best_val}")
    return {"aggregator": best_name, "toAmount": int(best_val)}
