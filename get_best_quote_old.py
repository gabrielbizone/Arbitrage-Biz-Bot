import requests

# Define aggregator configurations: base URL and parameter builder
AGGREGATORS = {
    "1inch": {
        "url_template": "https://api.1inch.io/v4.0/{chain_id}/quote",
        "params": lambda from_token, to_token, amount: {
            "fromTokenAddress": from_token,
            "toTokenAddress": to_token,
            "amount": str(amount),
        },
    },
    "0x": {
        "url_template": "https://api.0x.org/swap/v1/quote",
        "params": lambda from_token, to_token, amount: {
            "sellToken": from_token,
            "buyToken": to_token,
            "sellAmount": str(amount),
        },
    },
    "KyberSwap": {
        "url_template": "https://aggregator-api.kyberswap.com/v1/quote",
        "params": lambda from_token, to_token, amount: {
            "tokenIn": from_token,
            "tokenOut": to_token,
            "amountIn": str(amount),
            "gasInclude": "true",
        },
    },
}

def get_best_quote(from_token: str, to_token: str, amount: int, chain_id: int):
    """
    Consulta diferentes agregadores (1inch, 0x e KyberSwap) e retorna a melhor cotação
    disponível para trocar `amount` do token `from_token` por `to_token` na rede `chain_id`.

    Parameters
    ----------
    from_token: str
        Endereço do token de entrada (ex: USDC)
    to_token: str
        Endereço do token de saída (ex: LINK)
    amount: int
        Quantidade em unidades inteiras do token de entrada
    chain_id: int
        ID da blockchain (Polygon = 137)

    Returns
    -------
    dict | None
        Um dicionário contendo o nome do agregador e o valor final (`toAmount`),
        ou None se nenhuma cotação foi obtida.
    """
    best_quote = None
    for name, cfg in AGGREGATORS.items():
        url = cfg["url_template"].format(chain_id=chain_id)
        params = cfg["params"](from_token, to_token, amount)
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # Mapear a resposta para obter a quantidade de saída
            if name == "1inch":
                # 1inch retorna toTokenAmount como string
                to_amount = int(data.get("toTokenAmount", 0))
            elif name == "0x":
                # 0x usa buyAmount (string)
                to_amount = int(data.get("buyAmount", 0))
            elif name == "KyberSwap":
                # KyberSwap geralmente usa amountOut (string)
                to_amount = int(data.get("amountOut", 0))
            else:
                continue

            quote = {"aggregator": name, "toAmount": to_amount}
            if not best_quote or to_amount > best_quote["toAmount"]:
                best_quote = quote

        except Exception:
            # Ignorar agregadores que falharem
            continue

    return best_quote
