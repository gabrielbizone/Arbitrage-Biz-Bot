# tokens_config.py — suporte a mais redes (use override por ENV para ativar).
# ENV para override (lista de endereços separados por vírgula):
#   TOKENS_1, TOKENS_10, TOKENS_56, TOKENS_100, TOKENS_137, TOKENS_250, TOKENS_42161, TOKENS_43114, TOKENS_8453

import os

_PREFERRED = ["USDC","USDT","DAI","WETH","WBTC","WMATIC","LINK","AAVE"]

TOKENS_BY_CHAIN = {
    1: {},           # Ethereum — defina via TOKENS_1 (gás alto; só ative se quiser)
    10: {},          # Optimism — defina via TOKENS_10
    56: {  # BNB Smart Chain
        "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
        "USDT": "0x55d398326f99059ff775485246999027b3197955",
        "DAI":  "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3",
        "WETH": "0x2170Ed0880ac9A755fd29B2688956BD959F933F",
        "WBTC": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
        "LINK": "0xF8A0BF9cF54Bb92F17374d9e9A321E6a111a51bD",
        "AAVE": "0xfb6115445Bff7b52FeB98650C87f44907E58f802",
    },
    100: {},         # Gnosis — defina via TOKENS_100
    137: {  # Polygon
        "USDC":   "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "DAI":    "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        "WETH":   "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "WBTC":   "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "LINK":   "0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39",
        "AAVE":   "0xd6df932a45c0f255f85145f286ea0b292b21c90b",
    },
    250: {},         # Fantom — defina via TOKENS_250
    42161: {  # Arbitrum
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "USDT": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
        "DAI":  "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1",
        "WETH": "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",
        "WBTC": "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f",
        "LINK": "0xf97f4df75117a78c1a5a0dbb814af92458539fb4",
        "AAVE": "0xba5bDe662c17e2aDFF1075610382B9B691296350",
    },
    43114: {},       # Avalanche — defina via TOKENS_43114
    8453: {},        # Base — defina via TOKENS_8453
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
