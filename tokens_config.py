# tokens_config.py — unificado (símbolos + decimais + base token)
# Mantém token_symbol()/token_label() e adiciona get_token_decimals().
import os

# ordem sugerida quando não houver override via ENV
_PREFERRED = ["USDC","USDT","DAI","WETH","WBTC","WMATIC","LINK","AAVE"]

# Mapas padrão (pode sobrescrever via TOKENS_<chain> no ENV)
TOKENS_BY_CHAIN = {
    137: {  # Polygon
        "USDC":   "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # 6
        "DAI":    "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",  # 18
        "WETH":   "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",  # 18
        "WBTC":   "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",  # 8
        "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # 18
        "LINK":   "0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39",  # 18
        "AAVE":   "0xd6df932a45c0f255f85145f286ea0b292b21c90b",  # 18
    },
    42161: {  # Arbitrum
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",  # 6 (USDC nativo)
        "USDT": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",  # 6
        "DAI":  "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1",  # 18
        "WETH": "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",  # 18
        "WBTC": "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f",  # 8
        "LINK": "0xf97f4df75117a78c1a5a0dbb814af92458539fb4",  # 18
        "AAVE": "0xba5bDe662c17e2aDFF1075610382B9B691296350",  # 18
    },
    56: {  # BSC
        "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",  # 18 (BEP-20)
        "USDT": "0x55d398326f99059ff775485246999027b3197955",  # 18
        "DAI":  "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3",  # 18
        "WETH": "0x2170Ed0880ac9A755fd29B2688956BD959F933F",  # 18
        "WBTC": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",  # 18 (BTCB)
        "LINK": "0xF8A0BF9cF54Bb92F17374d9e9A321E6a111a51bD",  # 18
        "AAVE": "0xfb6115445Bff7b52FeB98650C87f44907E58f802",  # 18
    },
}

# Decimais conhecidos por chain/contrato (fallback = 18)
DECIMALS_BY_CHAIN = {
    137: {
        TOKENS_BY_CHAIN[137]["USDC"].lower(): 6,
        TOKENS_BY_CHAIN[137]["DAI"].lower(): 18,
        TOKENS_BY_CHAIN[137]["WETH"].lower(): 18,
        TOKENS_BY_CHAIN[137]["WBTC"].lower(): 8,
        TOKENS_BY_CHAIN[137]["WMATIC"].lower(): 18,
        TOKENS_BY_CHAIN[137]["LINK"].lower(): 18,
        TOKENS_BY_CHAIN[137]["AAVE"].lower(): 18,
    },
    42161: {
        TOKENS_BY_CHAIN[42161]["USDC"].lower(): 6,
        TOKENS_BY_CHAIN[42161]["USDT"].lower(): 6,
        TOKENS_BY_CHAIN[42161]["DAI"].lower(): 18,
        TOKENS_BY_CHAIN[42161]["WETH"].lower(): 18,
        TOKENS_BY_CHAIN[42161]["WBTC"].lower(): 8,
        TOKENS_BY_CHAIN[42161]["LINK"].lower(): 18,
        TOKENS_BY_CHAIN[42161]["AAVE"].lower(): 18,
    },
    56: {
        TOKENS_BY_CHAIN[56]["USDC"].lower(): 18,
        TOKENS_BY_CHAIN[56]["USDT"].lower(): 18,
        TOKENS_BY_CHAIN[56]["DAI"].lower(): 18,
        TOKENS_BY_CHAIN[56]["WETH"].lower(): 18,
        TOKENS_BY_CHAIN[56]["WBTC"].lower(): 18,
        TOKENS_BY_CHAIN[56]["LINK"].lower(): 18,
        TOKENS_BY_CHAIN[56]["AAVE"].lower(): 18,
    },
}

# Token base por chain (pode sobrescrever com BASE_TOKEN_<chain> no ENV)
BASE_TOKEN_BY_CHAIN = {
    137: TOKENS_BY_CHAIN[137]["USDC"],
    42161: TOKENS_BY_CHAIN[42161]["USDC"],
    56:  TOKENS_BY_CHAIN[56]["USDC"],
}

def _parse_addr_list(s: str):
    if not s:
        return []
    out = []
    for x in s.split(","):
        a = x.strip()
        if a.lower().startswith("0x") and len(a) == 42:
            out.append(a)
    return out

def get_default_tokens_for_chain(chain_id: int):
    env_key = f"TOKENS_{chain_id}"
    from_env = _parse_addr_list(os.getenv(env_key, ""))
    if from_env:
        return from_env
    m = TOKENS_BY_CHAIN.get(chain_id, {})
    return [m[k] for k in _PREFERRED if k in m]

def get_base_token_for_chain(chain_id: int):
    env_key = f"BASE_TOKEN_{chain_id}"
    v = os.getenv(env_key)
    if v and v.lower().startswith("0x") and len(v)==42:
        return v
    return BASE_TOKEN_BY_CHAIN.get(chain_id)

def get_token_decimals(chain_id: int, addr: str) -> int:
    """Retorna os decimais do token (fallback 18)."""
    return DECIMALS_BY_CHAIN.get(chain_id, {}).get((addr or '').lower(), 18)

# Mapa inverso para rotular/simbolizar
_INVERSE_BY_CHAIN = {
    cid: {addr.lower(): sym for sym, addr in mapping.items()}
    for cid, mapping in TOKENS_BY_CHAIN.items()
}

def token_label(addr: str, chain_id: int) -> str:
    """SYMBOL[sufixo] se conhecido; caso contrário 0x…abcd."""
    sym = _INVERSE_BY_CHAIN.get(chain_id, {}).get((addr or '').lower())
    suf = (addr or '')[-4:].lower() if addr else "????"
    return f"{sym}[{suf}]" if sym else f"0x…{suf}"

def token_symbol(addr: str, chain_id: int) -> str:
    """Apenas o símbolo ou 'UNKNOWN' se não mapeado."""
    return _INVERSE_BY_CHAIN.get(chain_id, {}).get((addr or '').lower(), "UNKNOWN")
