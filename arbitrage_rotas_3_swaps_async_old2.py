import time
from itertools import permutations
from get_best_quote_async import get_best_quote_async
from utils import net_percent

async def buscar_arbitragem_triangulo_async(session, tokens, amount, chain_id, log_thr, alert_thr, fee_bps_per_swap, collector, notifier):
    for token_a, token_b, token_c in permutations(tokens, 3):
        quote_ab = await get_best_quote_async(session, token_a, token_b, amount, chain_id)
        if not quote_ab:
            continue

        quote_bc = await get_best_quote_async(session, token_b, token_c, quote_ab["toAmount"], chain_id)
        if not quote_bc:
            continue

        quote_ca = await get_best_quote_async(session, token_c, token_a, quote_bc["toAmount"], chain_id)
        if not quote_ca:
            continue

        retorno_final = quote_ca["toAmount"] - amount
        gross = (retorno_final / amount) * 100.0
        net = net_percent(gross, swaps=3, fee_bps_per_swap=fee_bps_per_swap)

        msg = (
            f"TRI {token_a[-4:]}→{token_b[-4:]}→{token_c[-4:]}→{token_a[-4:]} "
            f"gross {gross:.2f}% | net {net:.2f}% "
            f"via {quote_ab['aggregator']} + {quote_bc['aggregator']} + {quote_ca['aggregator']}"
        )
        collector.append((net, msg, "TRI", chain_id, amount))

        if net >= log_thr:
            notifier('log', msg)
            if net >= alert_thr:
                notifier('alert', msg)
