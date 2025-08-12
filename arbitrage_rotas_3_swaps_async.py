
import time
from itertools import permutations
from get_best_quote_async import get_best_quote_async
from utils import net_percent
from tokens_config import token_label

async def buscar_arbitragem_triangulo_async(session, tokens, amount, chain_id, log_thr, alert_thr, fee_bps_per_swap, collector, notifier, sanity_cap):
    """Arbitragem com três swaps (A->B->C->A) entre todos os trios de tokens."""
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

        la = token_label(token_a, chain_id)
        lb = token_label(token_b, chain_id)
        lc = token_label(token_c, chain_id)

        msg = (
            f"TRI {la}→{lb}→{lc}→{la} "
            f"gross {gross:.2f}% | net {net:.2f}% "
            f"via {quote_ab['aggregator']} + {quote_bc['aggregator']} + {quote_ca['aggregator']}"
        )

        collector.append((net, msg, "TRI", chain_id, amount))

        # sanity cap para evitar absurdos (ex.: 2000%)
        if net > sanity_cap:
            print(f"[{time.strftime('%H:%M:%S')}] SUSPEITO (acima de {sanity_cap:.2f}%): {msg}")
            continue

        if net >= log_thr:
            notifier('log', msg)
            if net >= alert_thr:
                notifier('alert', msg)
