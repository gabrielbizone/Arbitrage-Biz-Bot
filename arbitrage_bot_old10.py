import os
import asyncio
import time
import aiohttp

from tokens_config import get_default_tokens_for_chain
from get_best_quote_async import get_best_quote_async
from arbitrage_rotas_3_swaps_async import buscar_arbitragem_triangulo_async
from telegram_notify import send_telegram
from utils import net_percent

def _parse_amounts_usdc(env_value: str):
    vals = []
    for x in (env_value or "50,100,250").split(","):
        x = x.strip()
        if not x:
            continue
        vals.append(int(float(x))*10**6)
    return vals

async def buscar_arbitragem_simples_async(session, tokens, amount, chain_id, log_thr, alert_thr, fee_bps, collector, notifier):
    for i, token_a in enumerate(tokens):
        for j, token_b in enumerate(tokens):
            if i == j:
                continue

            quote_ab = await get_best_quote_async(session, token_a, token_b, amount, chain_id)
            if not quote_ab:
                continue

            quote_ba = await get_best_quote_async(session, token_b, token_a, quote_ab["toAmount"], chain_id)
            if not quote_ba:
                continue

            retorno_final = quote_ba["toAmount"] - amount
            gross = (retorno_final / amount) * 100.0
            net = net_percent(gross, swaps=2, fee_bps_per_swap=fee_bps)

            msg = (
                f"SIMPLES {token_a[-4:]}→{token_b[-4:]}→{token_a[-4:]} "
                f"gross {gross:.2f}% | net {net:.2f}% "
                f"via {quote_ab['aggregator']} + {quote_ba['aggregator']}"
            )
            collector.append((net, msg, "SIMPLES", chain_id, amount))

            if net >= log_thr:
                notifier('log', msg)
                if net >= alert_thr:
                    notifier('alert', msg)

async def main_loop():
    CHAIN_IDS = [int(x) for x in (os.getenv("CHAIN_IDS","137").split(","))]
    AMOUNTS = _parse_amounts_usdc(os.getenv("AMOUNTS_USDC","50,100,250"))
    LOG_THR = float(os.getenv("LOG_THRESHOLD_PERCENT","0.2"))
    ALERT_THR = float(os.getenv("ALERT_THRESHOLD_PERCENT","0.6"))
    FEE_BPS = float(os.getenv("FEE_BPS_PER_SWAP","5"))
    INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS","30"))
    ONE_SHOT = os.getenv("ONE_SHOT","0") == "1"

    ALWAYS_SUMMARY = os.getenv("ALWAYS_SUMMARY","1") == "1"
    SUMMARY_TOP_K = int(os.getenv("SUMMARY_TOP_K","3"))
    HEARTBEAT_EVERY = int(os.getenv("HEARTBEAT_EVERY_CYCLES","20"))
    HEARTBEAT_TAG = os.getenv("HEARTBEAT_TAG","heartbeat")

    cycle = 0

    async with aiohttp.ClientSession(headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36",
        "Accept": "application/json",
    }) as session:
        def notifier(kind: str, msg: str):
            print(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if kind == 'alert':
                send_telegram(msg)

        async def run_once():
            nonlocal cycle
            cycle += 1
            found = []  # (net, msg, tipo, chain_id, amount)

            for chain_id in CHAIN_IDS:
                tokens = get_default_tokens_for_chain(chain_id)
                if not tokens or len(tokens) < 2:
                    print(f"⚠️ Sem tokens configurados para chain {chain_id}")
                    continue
                for amount in AMOUNTS:
                    await buscar_arbitragem_simples_async(session, tokens, amount, chain_id, LOG_THR, ALERT_THR, FEE_BPS, found, notifier)
                    await buscar_arbitragem_triangulo_async(session, tokens, amount, chain_id, LOG_THR, ALERT_THR, FEE_BPS, found, notifier)

            if ALWAYS_SUMMARY and found:
                top = sorted(found, key=lambda x: x[0], reverse=True)[:SUMMARY_TOP_K]
                linhas = [f"{i+1}. {t} chain {cid} amt {amt//10**6}→ net {net:.2f}% | {msg.split(' ',1)[1]}" for i,(net,msg,t,cid,amt) in enumerate(top)]
                texto = "Resumo do ciclo:\n" + "\n".join(linhas)
                send_telegram(texto)
            elif ALWAYS_SUMMARY and not found:
                send_telegram("Resumo do ciclo: nenhum par/trio retornou cotação válida (todos os agregadores falharam).")

            if HEARTBEAT_EVERY > 0 and cycle % HEARTBEAT_EVERY == 0:
                send_telegram(f"{HEARTBEAT_TAG}: vivo às {time.strftime('%H:%M:%S')} | chains={CHAIN_IDS} | amounts={[a//10**6 for a in AMOUNTS]} | log={LOG_THR}% | alert={ALERT_THR}%")

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
