
import time
from itertools import permutations
from get_best_quote_async import get_best_quote_async
from utils import net_percent
from tokens_config import token_symbol

async def buscar_arbitragem_triangulo_base_async(session, base_token, other_tokens, amount_in_base, chain_id, log_thr, alert_thr, fee_bps_per_swap, collector, notifier, sanity_cap, recheck_thr, recheck_tol):
    la = token_symbol(base_token, chain_id)
    for token_b, token_c in permutations(other_tokens, 2):
        lb = token_symbol(token_b, chain_id)
        lc = token_symbol(token_c, chain_id)

        q_ab = await get_best_quote_async(session, base_token, token_b, amount_in_base, chain_id)
        if not q_ab: continue

        q_bc = await get_best_quote_async(session, token_b, token_c, q_ab["toAmount"], chain_id)
        if not q_bc: continue

        q_ca = await get_best_quote_async(session, token_c, base_token, q_bc["toAmount"], chain_id)
        if not q_ca: continue

        retorno_final = q_ca["toAmount"] - amount_in_base
        gross = (retorno_final / amount_in_base) * 100.0
        net = net_percent(gross, swaps=3, fee_bps_per_swap=fee_bps_per_swap)

        msg = (
            f"TRI {la}→{lb}→{lc}→{la} "
            f"gross {gross:.2f}% | net {net:.2f}% "
            f"via {q_ab['aggregator']} + {q_bc['aggregator']} + {q_ca['aggregator']}"
        )
        collector.append((net, msg, "TRI", chain_id, amount_in_base))

        if net > sanity_cap:
            print(f"[{time.strftime('%H:%M:%S')}] SUSPEITO (>{sanity_cap:.2f}%): {msg}")
            continue

        if recheck_thr > 0 and net >= recheck_thr:
            non_ps = ["1inch","0x","KyberSwap","OpenOcean","Odos"]
            rq_ab = await get_best_quote_async(session, base_token, token_b, amount_in_base, chain_id, aggregator_list=non_ps)
            if not rq_ab: continue
            rq_bc = await get_best_quote_async(session, token_b, token_c, rq_ab["toAmount"], chain_id, aggregator_list=non_ps)
            if not rq_bc: continue
            rq_ca = await get_best_quote_async(session, token_c, base_token, rq_bc["toAmount"], chain_id, aggregator_list=non_ps)
            if not rq_ca: continue

            r_ret = rq_ca["toAmount"] - amount_in_base
            r_net = net_percent((r_ret/amount_in_base)*100.0, swaps=3, fee_bps_per_swap=fee_bps_per_swap)
            if abs(r_net - net) > recheck_tol:
                print(f"[{time.strftime('%H:%M:%S')}] TRI descartada no recheck (Δ>{recheck_tol:.2f}%). antes={net:.2f}% depois={r_net:.2f}% | {msg}")
                continue

        if net >= log_thr:
            notifier('log', msg)
            if net >= alert_thr:
                notifier('alert', msg)
