
import asyncio
import aiohttp
import os
import random

DEBUG = str(os.getenv("DEBUG", "0")).lower() in {"1", "true", "yes"}

def _log(msg: str):
    if DEBUG:
        print(msg)

def _openocean_chain_name(chain_id: int):
    return {
        1: "eth",
        56: "bsc",
        137: "polygon",
        42161: "arbitrum",
        10: "optimism",
        8453: "base",
        43114: "avalanche",
        250: "fantom",
    }.get(chain_id)

def _0x_base_url(chain_id: int):
    return {
        1: "https://api.0x.org",
        56: "https://bsc.api.0x.org",
        137: "https://polygon.api.0x.org",
        42161: "https://arbitrum.api.0x.org",
        10: "https://optimism.api.0x.org",
        8453: "https://base.api.0x.org",
        43114: "https://avalanche.api.0x.org",
        250: "https://fantom.api.0x.org",
    }.get(chain_id)

def _kyber_chain_slug(chain_id: int):
    return {
        1: "ethereum",
        56: "bsc",
        137: "polygon",
        42161: "arbitrum",
        10: "optimism",
        8453: "base",
        43114: "avalanche",
        250: "fantom",
    }.get(chain_id)

def _aggregators_for_chain(chain_id: int):
    env_key = f"AGGREGATORS_{chain_id}"
    v = os.getenv(env_key)
    if v:
        return [x.strip() for x in v.split(",") if x.strip()]
    return [x.strip() for x in os.getenv("AGGREGATORS", "1inch,0x,KyberSwap,Odos,OpenOcean,ParaSwap").split(",") if x.strip()]

async def _fetch_json(session, method, url, name, **kwargs):
    try:
        timeout = aiohttp.ClientTimeout(total=18)
        async with session.request(method, url, timeout=timeout, **kwargs) as resp:
            txt = await resp.text()
            if resp.status != 200:
                _log(f"[{name}] HTTP {resp.status} → {url}\n{txt[:240]}")
                return None
            ct = resp.headers.get("content-type","")
            if "json" not in ct:
                _log(f"[{name}] Unexpected content-type: {ct} → {url}")
                return None
            try:
                return await resp.json()
            except Exception as e:
                _log(f"[{name}] JSON decode error: {e} | body={txt[:200]}")
                return None
    except Exception as e:
        _log(f"[{name}] Exception: {e.__class__.__name__}: {e}")
        return None

# ------------- Aggregators -------------

async def _quote_1inch(session, chain_id, from_token, to_token, amount):
    name = "1inch"
    api_key = os.getenv("ONEINCH_API_KEY") or os.getenv("INCH_API_KEY") or os.getenv("ONEINCH_API_TOKEN")

    # Prefer v6 (api.1inch.dev) if API key is present
    if api_key:
        url6 = f"https://api.1inch.dev/swap/v6.0/{chain_id}/quote"
        params6a = {"src": from_token, "dst": to_token, "amount": str(amount)}
        headers = {"Authorization": f"Bearer {api_key}", "X-API-KEY": api_key}
        data = await _fetch_json(session, "GET", url6, name, params=params6a, headers=headers)
        if data and data.get("dstAmount") and str(data.get("dstAmount")).isdigit():
            return int(data["dstAmount"])
        # fallback: classic param names (alguns proxies aceitam)
        params6b = {"fromTokenAddress": from_token, "toTokenAddress": to_token, "amount": str(amount)}
        data = await _fetch_json(session, "GET", url6, name, params=params6b, headers=headers)
        if data and data.get("dstAmount") and str(data.get("dstAmount")).isdigit():
            return int(data["dstAmount"])

    # Fallback aberto v5 (pode ser bloqueado em alguns hosts)
    url5 = f"https://api.1inch.io/v5.0/{chain_id}/quote"
    params5a = {"src": from_token, "dst": to_token, "amount": str(amount)}
    data = await _fetch_json(session, "GET", url5, name, params=params5a)
    if data and data.get("dstAmount") and str(data.get("dstAmount")).isdigit():
        return int(data["dstAmount"])
    params5b = {"fromTokenAddress": from_token, "toTokenAddress": to_token, "amount": str(amount)}
    data = await _fetch_json(session, "GET", url5, name, params=params5b)
    if data and data.get("toTokenAmount") and str(data.get("toTokenAmount")).isdigit():
        return int(data["toTokenAmount"])

    # v4 (muitos locais ainda servem)
    url4 = f"https://api.1inch.io/v4.0/{chain_id}/quote"
    data = await _fetch_json(session, "GET", url4, name, params=params5b)
    if data and data.get("toTokenAmount") and str(data.get("toTokenAmount")).isdigit():
        return int(data["toTokenAmount"])

    return None

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
    if not val or not str(val).isdigit():
        _log(f"[{name}] missing buyAmount")
        return None
    return int(val)

async def _quote_kyber(session, chain_id, from_token, to_token, amount):
    name = "KyberSwap"
    slug = _kyber_chain_slug(chain_id)
    if not slug:
        _log(f"[{name}] unsupported chain_id {chain_id}")
        return None
    url = f"https://aggregator-api.kyberswap.com/{slug}/route/encode"
    params = {"tokenIn": from_token, "tokenOut": to_token, "amountIn": str(amount), "saveGas": "1", "chainId": str(chain_id)}
    data = await _fetch_json(session, "GET", url, name, params=params)
    if data and data.get("amountOut") and str(data.get("amountOut")).isdigit():
        return int(data["amountOut"])
    data = await _fetch_json(session, "POST", url, name, json=params)
    if data and data.get("amountOut") and str(data.get("amountOut")).isdigit():
        return int(data["amountOut"])
    url2 = f"https://aggregator-api.kyberswap.com/{slug}/api/v1/routes"
    params2 = {"tokenIn": from_token, "tokenOut": to_token, "amountIn": str(amount)}
    data = await _fetch_json(session, "GET", url2, name, params=params2)
    if data and isinstance(data.get("data"), dict):
        aout = data["data"].get("routeSummary", {}).get("amountOut")
        if aout and str(aout).isdigit():
            return int(aout)
    return None

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
        if val and str(val).isdigit():
            return int(val)
    except Exception:
        pass
    return None

async def _quote_odos(session, chain_id, from_token, to_token, amount):
    name = "Odos"
    url = "https://api.odos.xyz/sor/quote"
    payload = {"chainId": int(chain_id),"inputTokens": [{"tokenAddress": from_token, "amount": str(amount)}],"outputTokens": [{"tokenAddress": to_token, "proportion": 1}],"slippageLimitPercent": 0.5}
    data = await _fetch_json(session, "POST", url, name, json=payload)
    if not data: return None
    val = data.get("outAmount")
    if val is None:
        out_amounts = data.get("outAmounts")
        if isinstance(out_amounts, list) and out_amounts and str(out_amounts[0]).isdigit():
            val = out_amounts[0]
    if val is None or not str(val).isdigit():
        _log(f"[{name}] missing outAmount(s)")
        return None
    return int(val)

async def _quote_paraswap(session, chain_id, from_token, to_token, amount):
    name = "ParaSwap"
    url = "https://apiv5.paraswap.io/prices"
    params = {
        "network": str(chain_id),
        "srcToken": from_token,
        "destToken": to_token,
        "amount": str(amount),
        "side": "SELL",
        "srcDecimals": os.getenv("SRC_DECIMALS_OVERRIDE",""),
        "destDecimals": os.getenv("DEST_DECIMALS_OVERRIDE",""),
    }
    headers = {"Accept": "application/json"}
    data = await _fetch_json(session, "GET", url, name, params={k:v for k,v in params.items() if v!=""}, headers=headers)
    if not data: return None
    pr = data.get("priceRoute") or {}
    val = pr.get("destAmount")
    if not val or not str(val).isdigit():
        _log(f"[{name}] missing priceRoute.destAmount")
        return None
    return int(val)

async def _with_retry(coro_factory, attempts=2, delay=0.25):
    last = None
    for _ in range(attempts):
        last = await coro_factory()
        if last is not None:
            return last
        await asyncio.sleep(delay)
    return last

async def get_best_quote_async(session, from_token: str, to_token: str, amount: int, chain_id: int = 137, aggregator_list=None):
    order = aggregator_list or _aggregators_for_chain(chain_id)
    if aggregator_list is None and os.getenv("AGGREGATORS") is None and os.getenv(f"AGGREGATORS_{chain_id}") is None:
        order = order.copy()
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
    return {"aggregator": best_name, "toAmount": int(best_val)}
