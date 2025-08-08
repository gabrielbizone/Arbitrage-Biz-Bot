
from modules.get_best_quote import get_best_quote
import time

def buscar_arbitragem_triangulo(tokens, amount, chain_id):
    for rota in permutations(tokens, 3):
        token_a, token_b, token_c = rota
        quote_ab = get_best_quote(token_a, token_b, amount, chain_id)
        if not quote_ab:
            continue

        quote_bc = get_best_quote(token_b, token_c, quote_ab["toAmount"], chain_id)
        if not quote_bc:
            continue

        quote_ca = get_best_quote(token_c, token_a, quote_bc["toAmount"], chain_id)
        if not quote_ca:
            continue

        retorno_final = quote_ca["toAmount"] - amount
        percentual = (retorno_final / amount) * 100
        if percentual > 0.5:
            print(f"[{time.strftime('%H:%M:%S')}] {token_a} → {token_b} → {token_c} → {token_a} = {percentual:.2f}% via {quote_ab['aggregator']} + {quote_bc['aggregator']} + {quote_ca['aggregator']}")
