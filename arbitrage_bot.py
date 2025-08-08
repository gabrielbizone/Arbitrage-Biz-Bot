import time
from get_best_quote import get_best_quote
from arbitrage_rotas_3_swaps import buscar_arbitragem_triangulo

# Lista de tokens (endereços na Polygon)
USDC   = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
LINK   = "0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39"
WMATIC = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
AAVE   = "0xd6df932a45c0f255f85145f286ea0b292b21c90b"

tokens   = [USDC, LINK, WMATIC, AAVE]
amount   = 100 * 10**6  # 100 USDC (6 decimais)
chain_id = 137          # Polygon

def buscar_arbitragem_simples(tokens, amount, chain_id):
    """Procura arbitragem simples (duas trocas) entre todos os pares de tokens."""
    for token_a in tokens:
        for token_b in tokens:
            if token_a == token_b:
                continue

            # Primeira perna: token_a -> token_b
            quote_ab = get_best_quote(token_a, token_b, amount, chain_id)
            if not quote_ab:
                continue

            # Segunda perna: token_b -> token_a
            quote_ba = get_best_quote(token_b, token_a, quote_ab["toAmount"], chain_id)
            if not quote_ba:
                continue

            retorno_final = quote_ba["toAmount"] - amount
            percentual = (retorno_final / amount) * 100

            if percentual > 0.5:
                print(
                    f"[{time.strftime('%H:%M:%S')}] "
                    f"SIMPLES {token_a[-4:]} → {token_b[-4:]} → {token_a[-4:]} = {percentual:.2f}% "
                    f"via {quote_ab['aggregator']} + {quote_ba['aggregator']}"
                )

if __name__ == "__main__":
    print("🔁 Buscando oportunidades de arbitragem (simples e triangulares)...")
    buscar_arbitragem_simples(tokens, amount, chain_id)
    buscar_arbitragem_triangulo(tokens, amount, chain_id)
