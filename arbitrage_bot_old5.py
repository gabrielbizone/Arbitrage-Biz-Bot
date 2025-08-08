import requests

def get_best_quote(token_in, token_out, amount, chain_id):
    """
    Consulta múltiplos agregadores e retorna o melhor resultado (maior retorno).
    """
    aggregators = {
        "1inch": f"https://api.1inch.io/v4.0/{chain_id}/quote?fromTokenAddress={token_in}&toTokenAddress={token_out}&amount={amount}",
        "0x": f"https://api.0x.org/swap/v1/quote?buyToken={token_out}&sellToken={token_in}&sellAmount={amount}",
        "kyberswap": f"https://aggregator-api.kyberswap.com/{chain_id}/api/v1/routes?tokenIn={token_in}&tokenOut={token_out}&amountIn={amount}"
    }

    best_quote = None
    best_return = 0

    for name, url in aggregators.items():
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                to_amount = 0
                if name == "1inch":
                    to_amount = int(data.get("toTokenAmount", 0))
                elif name == "0x":
                    to_amount = int(data.get("buyAmount", 0))
                elif name == "kyberswap":
                    to_amount = int(data.get("data", {}).get("routeSummary", {}).get("amountOut", 0))

                if to_amount > best_return:
                    best_return = to_amount
                    best_quote = {"aggregator": name, "toAmount": to_amount, "data": data}
        except Exception:
            continue

    return best_quote
