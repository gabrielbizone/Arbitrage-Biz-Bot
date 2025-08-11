import asyncio
import time
from itertools import permutations
from get_best_quote_async import get_best_quote_async
from utils import net_percent
from telegram_notify import send_telegram

async def buscar_arbitragem_triangulo_async(session, tokens, amount, chain_id, log_thr, alert_thr, fee_bps_per_swap):
    """Arbitragem com três swaps (rota triangular) entre todos os trios de tokens.
    Faz log quando % líquido >= log_thr; envia Telegram quando % líquido >= alert_thr.
    """
    for token_a, token_b, token_c in permutations(tokens, 3):
        # 1ª perna
        quote_ab = await get_best_quote_async(session, token_a, token_b, amount, chain_id)
        if not quote_ab:
            continue

        # 2ª perna
        quote_bc = await get_best_quote_async(session, token_b, token_c, quote_ab["toAmount"], chain_id)
        if not quote_bc:
            continue

        # 3ª perna
        quote_ca = await get_best_quote_async(session, token_c, token_a, quote_bc["toAmount"], chain_id)
        if not quote_ca:
            continue

        retorno_final = quote_ca["toAmount"] - amount
        gross = (retorno_final / amount) * 100.0
        net = net_percent(gross, swaps=3, fee_bps_per_swap=fee_bps_per_swap)

        if net >= log_thr:
            msg = (
                f"[{time.strftime('%H:%M:%S')}] TRI "
                f"{token_a[-4:]}→{token_b[-4:]}→{token_c[-4:]}→{token_a[-4:]} "
                f"gross {gross:.2f}% | net {net:.2f}% "
                f"via {quote_ab['aggregator']} + {quote_bc['aggregator']} + {quote_ca['aggregator']}"
            )
            print(msg)
            if net >= alert_thr:
                send_telegram(msg)
