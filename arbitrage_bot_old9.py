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

async def buscar_arbitragem_simples_async(session, tokens, amount, chain_id, log_thr, alert_thr, fee_bps):
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

            if net >= log_thr:
                msg = (
                    f"[{time.strftime('%H:%M:%S')}] SIMPLES "
                    f"{token_a[-4:]}→{token_b[-4:]}→{token_a[-4:]} "
                    f"gross {gross:.2f}% | net {net:.2f}% "
                    f"via {quote_ab['aggregator']} + {quote_ba['aggregator']}"
                )
                print(msg)
                if net >= alert_thr:
                    send_telegram(msg)

async def main_loop():
    CHAIN_IDS = [int(x) for x in (os.getenv("CHAIN_IDS","137").split(","))]
    AMOUNTS = _parse_amounts_usdc(os.getenv("AMOUNTS_USDC","50,100,250"))
    LOG_THR = float(os.getenv("LOG_THRESHOLD_PERCENT","0.2"))
    ALERT_THR = float(os.getenv("ALERT_THRESHOLD_PERCENT","0.6"))
    FEE_BPS = float(os.getenv("FEE_BPS_PER_SWAP","5"))  # 0.05% por swap
    INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS","30"))
    ONE_SHOT = os.getenv("ONE_SHOT","0") == "1"

    async with aiohttp.ClientSession() as session:
        async def run_once():
            for chain_id in CHAIN_IDS:
                tokens = get_default_tokens_for_chain(chain_id)
                if not tokens or len(tokens) < 2:
                    print(f"⚠️ Sem tokens configurados para chain {chain_id}")
                    continue
                for amount in AMOUNTS:
                    await buscar_arbitragem_simples_async(session, tokens, amount, chain_id, LOG_THR, ALERT_THR, FEE_BPS)
                    await buscar_arbitragem_triangulo_async(session, tokens, amount, chain_id, LOG_THR, ALERT_THR, FEE_BPS)

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
