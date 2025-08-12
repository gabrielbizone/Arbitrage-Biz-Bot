import asyncio
import aiohttp
import os
import random

DEBUG = str(os.getenv("DEBUG", "0")).lower() in {"1", "true", "yes"}

def _log(msg: str):
    if DEBUG:
        print(msg)

def _openocean_chain_name(chain_id: int):
    mapping = {1:"eth",56:"bsc",137:"polygon",42161:"arbitrum",10:"optimism",8453:"base",43114:"avalanche",250:"fantom"}
    return mapping.get(chain_id)

def _0x_base_url(chain_id: int):
    mapping = {1:"https://api.0x.org",56:"https://bsc.api.0x.org",137:"https://polygon.api.0x.org",42161:"https://arbitrum.api.0x.org",10:"https://optimism.api.0x.org",8453:"https://base.api.0x.org",43114:"https://avalanche.api.0x.org",250:"https://fantom.api.0x.org"}
    return mapping.get(chain_id)

async def _fetch_json(session, method, url, name, **kwargs):
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with session.request(method, url, timeout=timeout, **kwargs) as resp:
            if resp.status != 200:
                _log(f"[{name}] HTTP {resp.status} -> {url}")
                return None
            ct = resp.headers.get("content-type","")
            if "json" not in ct:
                _log(f"[{name}] Unexpected content-type: {ct}")
            return await resp.json()
    except Exception as e:
        _log(f"[{name}] Exception: {e.__class__.__name__}: {e}")
        return None

async def _quote_1inch(session, chain_id, from_token, to_token, amount):
    name = "1inch"
    url = f"https://api.1inch.io/v4.0/{chain_id}/quote"
    params = {"fromTokenAddress": from_token, "toTokenAddress": to_token, "amount": str(amount)}
    data = await _fetch_json(session, "GET", url, name, params=params)
    if not data: return None
    val = data.get("toTokenAmount")
    if not val:
        _log(f"[{name}] missing toTokenAmount")
        return None
    _log(f"[{name}] toAmount={val}")
    return int(val)

async def _quote_0x(session, chain_id, from_token, to_token, amount):
    name = "0x"
    base = _0x_base_url(chain_id)
    if not base:
        _log(f"[{name}] unsupported chain_id {chain_id}")
        return None
    url = f"{base}/swap/v1/quote"
    params = {"sellToken": from_token, "buyToken": to_token, "sellAmount": str(amount), "skipValidation": "true"}
    data = await _fetch_json(session, "GET", url, name, params=params)
    if not data: return None
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
    if not data: return None
    val = data.get("amountOut")
    if not val:
        _log(f"[{name}] missing amountOut")
        return None
    _log(f"[{name}] toAmount={val}")
    return int(val)

async def _quote_openocean(session, chain_id, from_token, to_token, amount):
    name = "OpenOcean"
    chain = _openocean_chain_name(chain_id)
    if not chain:
        _log(f"[{name}] unsupported chain_id {chain_id}")
        return None
    url = f"https://open-api.openocean.finance/v3/{chain}/quote"
    params = {"inTokenAddress": from_token, "outTokenAddress": to_token, "amount": str(amount)}
    data = await _fetch_json(session, "GET", url, name, params=params)
    if not data: return None
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
    payload = {"chainId": int(chain_id),"inputTokens": [{"tokenAddress": from_token, "amount": str(amount)}],"outputTokens": [{"tokenAddress": to_token, "proportion": 1}],"slippageLimitPercent": 0.5}
    data = await _fetch_json(session, "POST", url, name, json=payload)
    if not data: return None
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

async def _quote_paraswap(session, chain_id, from_token, to_token, amount):
    name = "ParaSwap"
    url = "https://apiv5.paraswap.io/prices"
    params = {"network": str(chain_id),"srcToken": from_token,"destToken": to_token,"amount": str(amount),"side": "SELL"}
    headers = {"Accept": "application/json"}
    data = await _fetch_json(session, "GET", url, name, params=params, headers=headers)
    if not data: return None
    pr = data.get("priceRoute") or {}
    val = pr.get("destAmount")
    if not val:
        _log(f"[{name}] missing priceRoute.destAmount")
        return None
    _log(f"[{name}] toAmount={val}")
    try:
        return int(val)
    except Exception:
        return None

async def _with_retry(coro_factory, attempts=2, delay=0.2):
    last = None
    for _ in range(attempts):
        last = await coro_factory()
        if last is not None:
            return last
        await asyncio.sleep(delay)
    return last

async def get_best_quote_async(session, from_token: str, to_token: str, amount: int, chain_id: int = 137):
    order = os.getenv("AGGREGATORS", "1inch,0x,KyberSwap,OpenOcean,Odos,ParaSwap").split(",")
    order = [x.strip() for x in order if x.strip()]
    if os.getenv("AGGREGATORS") is None:
        random.shuffle(order)

    tasks = []
    for name in order:
        if name == "1inch":
            tasks.append(_with_retry(lambda: _quote_1inch(session, chain_id, from_token, to_token, amount)))
        elif name == "0x":
            tasks.append(_with_retry(lambda: _quote_0x(session, chain_id, from_token, to_token, amount)))
        elif name == "KyberSwap":
            tasks.append(_with_retry(lambda: _quote_kyber(session, chain_id, from_token, to_token, amount)))
        elif name == "OpenOcean":
            tasks.append(_with_retry(lambda: _quote_openocean(session, chain_id, from_token, to_token, amount)))
        elif name == "Odos":
            tasks.append(_with_retry(lambda: _quote_odos(session, chain_id, from_token, to_token, amount)))
        elif name == "ParaSwap":
            tasks.append(_with_retry(lambda: _quote_paraswap(session, chain_id, from_token, to_token, amount)))
        else:
            _log(f"[get_best_quote_async] unknown aggregator '{name}' — ignoring")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    best_val, best_name = None, None
    for name, val in zip(order, results):
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
