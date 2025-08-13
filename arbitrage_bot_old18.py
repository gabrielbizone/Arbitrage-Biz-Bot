
import os
import asyncio
import time
import aiohttp

from tokens_config import (
    get_default_tokens_for_chain,
    get_base_token_for_chain,
    get_token_decimals,
    token_symbol,
)
from get_best_quote_async import get_best_quote_async
from arbitrage_rotas_3_swaps_async import buscar_arbitragem_triangulo_base_async
from telegram_notify import send_telegram
from utils import net_percent

DEBUG = str(os.getenv("DEBUG", "0")).lower() in {"1", "true", "yes"}

def _log(msg: str):
    if DEBUG:
        print(msg)

def _parse_amounts_list(env_value: str):
    # retorna lista de floats em "unidades de USDC" (ex.: [10, 20, 50])
    vals = []
    for x in (env_value or "50,100,250").split(","):
        x = x.strip()
        if not x:
            continue
        vals.append(float(x))
    return vals

def _chain_name(chain_id: int) -> str:
    return {
        1: "Ethereum",
        10: "Optimism",
        56: "BNB Smart Chain",
        100: "Gnosis",
        137: "Polygon",
        250: "Fantom",
        42161: "Arbitrum",
        43114: "Avalanche",
        8453: "Base",
    }.get(chain_id, str(chain_id))

async def buscar_arbitragem_simples_base_async(session, base_token, other_tokens, amount_in_units, chain_id, log_thr, alert_thr, fee_bps, collector, notifier, sanity_cap, recheck_thr, recheck_tol):
    la = token_symbol(base_token, chain_id)
    chain = _chain_name(chain_id)

    for token_b in other_tokens:
        lb = token_symbol(token_b, chain_id)

        q_ab = await get_best_quote_async(session, base_token, token_b, amount_in_units, chain_id)
        if not q_ab:
            _log(f"[{chain}][SIMPLES] Falha BASE→X {la}→{lb}")
            continue

        q_ba = await get_best_quote_async(session, token_b, base_token, q_ab["toAmount"], chain_id)
        if not q_ba:
            _log(f"[{chain}][SIMPLES] Falha X→BASE {lb}→{la}")
            continue

        retorno_final = q_ba["toAmount"] - amount_in_units
        gross = (retorno_final / amount_in_units) * 100.0
        net = net_percent(gross, swaps=2, fee_bps_per_swap=fee_bps)

        msg = (
            f"[{chain}] SIMPLES {la}→{lb}→{la} "
            f"gross {gross:.2f}% | net {net:.2f}% "
            f"via {q_ab['aggregator']} + {q_ba['aggregator']}"
        )
        collector.append((net, msg, "SIMPLES", chain_id, amount_in_units))

        if net > sanity_cap:
            print(f"[{time.strftime('%H:%M:%S')}] SUSPEITO (>{sanity_cap:.2f}%): {msg}")
            continue

        if recheck_thr > 0 and net >= recheck_thr:
            non_ps = ["1inch","0x","KyberSwap","OpenOcean","Odos"]
            rq_ab = await get_best_quote_async(session, base_token, token_b, amount_in_units, chain_id, aggregator_list=non_ps)
            rq_ba = await get_best_quote_async(session, token_b, base_token, q_ab["toAmount"], chain_id, aggregator_list=non_ps) if rq_ab else None
            if not rq_ab or not rq_ba:
                print(f"[{time.strftime('%H:%M:%S')}] DESCARTADO: recheck sem consenso | {msg}")
                continue
            r_ret = rq_ba["toAmount"] - amount_in_units
            r_net = net_percent((r_ret/amount_in_units)*100.0, swaps=2, fee_bps_per_swap=fee_bps)
            if abs(r_net - net) > recheck_tol:
                print(f"[{time.strftime('%H:%M:%S')}] DESCARTADO no recheck (Δ>{recheck_tol:.2f}%). antes={net:.2f}% depois={r_net:.2f}% | {msg}")
                continue

        if net >= log_thr:
            notifier('log', msg)
            if net >= alert_thr:
                notifier('alert', msg)

async def main_loop():
    CHAIN_IDS = [int(x) for x in (os.getenv("CHAIN_IDS","137").split(","))]
    AMOUNTS_USDC = _parse_amounts_list(os.getenv("AMOUNTS_USDC","50,100,250"))  # floats em USDC
    LOG_THR = float(os.getenv("LOG_THRESHOLD_PERCENT","0.2"))
    ALERT_THR = float(os.getenv("ALERT_THRESHOLD_PERCENT","0.6"))
    FEE_BPS = float(os.getenv("FEE_BPS_PER_SWAP","5"))
    INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS","30"))
    ONE_SHOT = os.getenv("ONE_SHOT","0") == "1"

    ALWAYS_SUMMARY = os.getenv("ALWAYS_SUMMARY","1") == "1"
    SUMMARY_TOP_K = int(os.getenv("SUMMARY_TOP_K","3"))
    HEARTBEAT_EVERY = int(os.getenv("HEARTBEAT_EVERY_CYCLES","20"))
    HEARTBEAT_TAG = os.getenv("HEARTBEAT_TAG","heartbeat")
    SANITY_CAP = float(os.getenv("SANITY_MAX_NET_PERCENT","30"))
    RECHECK_THR = float(os.getenv("RECHECK_IF_NET_ABOVE","3"))
    RECHECK_TOL = float(os.getenv("RECHECK_TOLERANCE_PERCENT","0.5"))

    cycle = 0

    async with aiohttp.ClientSession(headers={
        "User-Agent": "Mozilla/5.0 (compatible; ArbitrBot/1.0)",
        "Accept": "application/json",
    }) as session:
        def notifier(kind: str, msg: str):
            print(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if kind == 'alert':
                send_telegram(msg)

        async def run_once():
            nonlocal cycle
            cycle += 1
            found = []

            for chain_id in CHAIN_IDS:
                base_token = get_base_token_for_chain(chain_id)
                tokens = get_default_tokens_for_chain(chain_id)
                other = [t for t in tokens if base_token and t.lower()!=base_token.lower()]

                if not base_token or not other:
                    print(f"⚠️ Config incompleta na {_chain_name(chain_id)}: base={base_token} tokens={len(other)}")
                    continue

                # decimais corretos para o token base desta chain
                base_decimals = get_token_decimals(chain_id, base_token)

                for amt_usdc in AMOUNTS_USDC:
                    amount_units = int(float(amt_usdc) * (10**base_decimals))  # ex.: BSC USDC = 18, Polygon USDC = 6
                    await buscar_arbitragem_simples_base_async(session, base_token, other, amount_units, chain_id, LOG_THR, ALERT_THR, FEE_BPS, found, notifier, SANITY_CAP, RECHECK_THR, RECHECK_TOL)
                    await buscar_arbitragem_triangulo_base_async(session, base_token, other, amount_units, chain_id, LOG_THR, ALERT_THR, FEE_BPS, found, notifier, SANITY_CAP, RECHECK_THR, RECHECK_TOL)

            # SUMÁRIO: nomes de chain e amt com unidade
            if ALWAYS_SUMMARY and found:
                top = sorted(found, key=lambda x: x[0], reverse=True)[:SUMMARY_TOP_K]
                linhas = []
                for i,(net,msg,t,cid,amt_units) in enumerate(top):
                    # converter amt_units para USDC (considerando decimais da chain do item)
                    base_token = get_base_token_for_chain(cid)
                    dec = get_token_decimals(cid, base_token)
                    amt_usdc = amt_units / (10**dec)
                    linhas.append(f"{i+1}. {t} chain {_chain_name(cid)} amt {amt_usdc:g} USDC→ net {net:.2f}% | {msg.split(' ',1)[1]}")
                send_telegram("Resumo do ciclo:\n" + "\n".join(linhas))
            elif ALWAYS_SUMMARY and not found:
                send_telegram("Resumo do ciclo: nenhum par/trio retornou cotação válida (todos os agregadores falharam).")

            if HEARTBEAT_EVERY > 0 and cycle % HEARTBEAT_EVERY == 0:
                names = [_chain_name(c) for c in CHAIN_IDS]
                amts = []
                for cid in CHAIN_IDS:
                    base_token = get_base_token_for_chain(cid)
                    dec = get_token_decimals(cid, base_token)
                    for a in AMOUNTS_USDC:
                        amts.append(a)  # já são USDC
                send_telegram(f"{HEARTBEAT_TAG}: vivo às {time.strftime('%H:%M:%S')} | chains={names} | amounts={AMOUNTS_USDC} USDC | log={LOG_THR}% | alert={ALERT_THR}%")

        if ONE_SHOT:
            await run_once()
        else:
            while True:
                await run_once()
                await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Encerrado.")
