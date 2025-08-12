[README_patch.md](https://github.com/user-attachments/files/21744484/README_patch.md)[README.md](https://github.com/user-attachments/files/21743377/README.md)

# Arbitrage Bot (Render Worker)

Bot assíncrono para varrer arbitragem **simples (2 swaps)** e **triangular (3 swaps)** em DEX via agregadores (1inch, 0x, KyberSwap, OpenOcean, Odos). Envia **alertas no Telegram** quando o % líquido ≥ limiar e **sempre** manda um **resumo por ciclo**. Feito para rodar como **Background Worker** no Render.

## Arquitetura
- `arbitrage_bot.py` — loop principal (varredura contínua), sumário por ciclo e heartbeat.
- `get_best_quote_async.py` — cotações assíncronas com 1inch, 0x, KyberSwap, OpenOcean, Odos (timeout, retry leve, cabeçalhos).
- `arbitrage_rotas_3_swaps_async.py` — arbitragem triangular.
- `tokens_config.py` — lista padrão de tokens por chain; **override via ENV** `TOKENS_<chain>`.
- `telegram_notify.py` — envio para Telegram.
- `utils.py` — utilitários (`net_percent`).
- `requirements.txt` — dependências.

## Como rodar no Render (Background Worker)
1. **New → Background Worker** e conecte seu repositório.[Uploading README_patch.md…]()

2. **Root Directory**: raiz do repo (ou subpasta se você usar).
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `python arbitrage_bot.py`

### Variáveis de ambiente
**Obrigatórias**
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

**Opcionais (com defaults)**
- `CHAIN_IDS` — ex.: `137,42161,56` (default `137`)
- `AMOUNTS_USDC` — ex.: `50,100,250` (em USDC) (default `50,100,250`)
- `LOG_THRESHOLD_PERCENT` — (default `0.2`)
- `ALERT_THRESHOLD_PERCENT` — (default `0.6`)
- `FEE_BPS_PER_SWAP` — (default `5` → 0,05% por swap)
- `SCAN_INTERVAL_SECONDS` — (default `30`)
- `ONE_SHOT` — `"0"` contínuo; `"1"` roda um ciclo e para
- `ALWAYS_SUMMARY` — `"1"` envia resumo a cada ciclo (default `1`)
- `SUMMARY_TOP_K` — (default `3`)
- `HEARTBEAT_EVERY_CYCLES` — (default `20`)
- `HEARTBEAT_TAG` — (default `heartbeat`)
- `DEBUG` — `"1"` para logs detalhados (default `0`)
- `PYTHONUNBUFFERED` — `"1"` para logs em tempo real
- `TOKENS_137` / `TOKENS_42161` / `TOKENS_56` — lista de **endereços** de tokens (se quiser sobrescrever os defaults da chain)

### Dicas rápidas
- Para **testar rápido**: `ONE_SHOT=1`, `CHAIN_IDS=137`, `AMOUNTS_USDC=10,20`, `DEBUG=1`, `PYTHONUNBUFFERED=1`.
- Se quiser **incluir USDT no Polygon**, defina `TOKENS_137` com o endereço exato do USDT que você usa.
- Logs e resumo ajudam a confirmar que o ciclo rodou mesmo quando não há oportunidades.

## Observações
- O bot **não executa swaps**, apenas encontra oportunidades e envia alertas.
- `% líquido` é aproximado (subtrai bps por swap). Ajuste `FEE_BPS_PER_SWAP` conforme sua realidade.# Patch: mais redes + ParaSwap

## O que inclui
- **Agregador novo:** ParaSwap (além de 1inch, 0x, KyberSwap, OpenOcean, Odos).
- **Mais redes suportadas:** Ethereum(1), Optimism(10), Base(8453), Avalanche(43114), Fantom(250), Gnosis(100), além de Polygon(137), Arbitrum(42161) e BSC(56).

## Como usar
1) Substitua no seu repo:
   - `get_best_quote_async.py`
   - `tokens_config.py`
2) (opcional) Escolha a ordem dos agregadores:
   - `AGGREGATORS=1inch,0x,KyberSwap,ParaSwap,Odos,OpenOcean`
3) Ative redes novas definindo tokens via ENV:
   - `TOKENS_<chainId>=addr1,addr2,addr3,...`
   - Ex.: Base (8453) com USDC + WETH:
     ```
     CHAIN_IDS=8453
     TOKENS_8453=0x833589fC... , 0x4200000000000000000000000000000000000006
     ```

> Dica: comece com 2–4 tokens por rede (USDC, WETH, USDT, DAI) e aumente depois.

