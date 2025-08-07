#!/usr/bin/env python3
"""
Simple triangular arbitrage bot for the Polygon network.

This script checks a handful of token pairs (USDC → token → USDC)
via the 1inch v4 API to see if swapping USDC into another token and
then immediately swapping back yields a positive return.  When the
potential profit exceeds a configurable percentage threshold, the bot
sends a notification via Telegram.

Key features:

* Uses the 1inch v4 API to quote token swaps without executing them.
* Supports a configurable list of tokens and their ERC‑20 addresses
  on Polygon along with their decimal precisions.
* Reads sensitive configuration (Telegram token, chat ID, profit
  threshold) from environment variables, with sensible defaults.  In
  particular, ``TELEGRAM_CHAT_ID`` defaults to the group ID provided
  by the user (``-4848266284``), so you can point messages at your
  Telegram group without changing the code.
* Handles network and JSON decode errors gracefully and simply skips
  tokens that cannot be quoted.

To run this script manually you need to set at least ``TELEGRAM_TOKEN``
in your environment.  You can optionally set ``PROFIT_THRESHOLD_PERCENT``
to adjust the minimum percentage gain required to trigger an alert.

Example:

    export TELEGRAM_TOKEN="your_bot_token"
    export TELEGRAM_CHAT_ID="-4848266284"  # optional, defaults to this value
    export PROFIT_THRESHOLD_PERCENT="1.5"   # alert only if >1.5% profit
    python arbitrage_bot_updated.py

"""

import datetime
import os
from typing import Dict, Optional

import pytz
import requests

CHAIN_ID: int = 137  # Polygon mainnet

# Address of USDC on Polygon (6 decimals)
USDC_ADDRESS: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_DECIMALS: int = 6

# Mapping of token symbol to its ERC‑20 address and decimals on Polygon
TOKENS: Dict[str, Dict[str, object]] = {
    # symbol: {'address': addr, 'decimals': decimals}
    "LINK": {
        "address": "0x53e0bca35ec356bd5dddfebbd1fc0fbd03fae4c6",
        "decimals": 18,
    },
    "AAVE": {
        "address": "0xd6Df932A45C0f255f85145f286eA0B292B21C90B",
        "decimals": 18,
    },
    "MATIC": {
        # wrapped MATIC address; native MATIC has no ERC‑20 token
        "address": "0x0000000000000000000000000000000000001010",
        "decimals": 18,
    },
    "WETH": {
        "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "decimals": 18,
    },
    "WBTC": {
        "address": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        "decimals": 8,
    },
    "CRV": {
        "address": "0x172370d5Cd63279eFa6d502DAB29171933a610AF",
        "decimals": 18,
    },
    "DAI": {
        "address": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        "decimals": 18,
    },
    "XSGD": {
        "address": "0xebF2096E01455108b7edF1Bda69113F3e5ceD0A7",
        "decimals": 18,
    },
}


def get_profit_threshold() -> float:
    """Return the minimum percentage profit required to trigger an alert.

    The function checks the ``PROFIT_THRESHOLD_PERCENT`` environment
    variable.  If present and valid, it converts it to a float.  If not
    set or not convertible to a float, it returns a default of 1.0
    percent.
    """
    value = os.getenv("PROFIT_THRESHOLD_PERCENT")
    if value is not None:
        try:
            return float(value)
        except ValueError:
            pass
    return 1.0


def get_telegram_credentials() -> (Optional[str], Optional[str]):
    """Retrieve the Telegram bot token and chat ID from the environment.

    ``TELEGRAM_TOKEN`` is required to send messages.  If no chat ID is
    provided via ``TELEGRAM_CHAT_ID``, the function falls back to
    ``-4848266284`` which corresponds to your group.  This means that
    without changing the code you can direct alerts to your group by
    either setting the environment variable or leaving it unset.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "-4848266284")
    return token, chat_id


def quote_swap(chain_id: int, from_addr: str, to_addr: str, amount: int) -> Optional[Dict[str, object]]:
    """Call the 1inch API to quote a swap from ``from_addr`` to ``to_addr``.

    Returns a dict with keys ``fromTokenAmount`` and ``toTokenAmount`` on
    success, or ``None`` if an error occurs (HTTP error, network
    exception or JSON decode error).  A timeout is used to prevent the
    request from hanging indefinitely.
    """
    url = f"https://api.1inch.io/v4.0/{chain_id}/quote"
    params = {
        "fromTokenAddress": from_addr,
        "toTokenAddress": to_addr,
        "amount": str(amount),
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as err:
        # Print and skip tokens that fail to quote
        print(f"Skipping swap from {from_addr} to {to_addr}: {err}")
        return None


def send_telegram_message(token: Optional[str], chat_id: Optional[str], message: str) -> None:
    """Send a plain‑text message via the Telegram Bot API.

    If either ``token`` or ``chat_id`` is ``None``, the function prints
    the message to stdout and returns without attempting to contact the
    Telegram servers.  This behaviour allows you to test the script
    without having a valid bot token configured.
    """
    if not token or not chat_id:
        print(f"[Telegram] {message}")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")


def perform_arbitrage_check() -> None:
    """Check each token for arbitrage opportunities and report via Telegram.

    The function uses a fixed principal amount of 1 USDC (1 * 10**USDC_DECIMALS)
    for quoting purposes.  It is not intended to execute trades; rather,
    it estimates whether arbitrage exists at the current moment.  If
    profitable opportunities exist beyond the configured threshold,
    they are summarised and sent via Telegram with a timestamp in
    America/Vancouver (PST/PDT) timezone.
    """
    token, chat_id = get_telegram_credentials()
    threshold = get_profit_threshold()

    # principal in smallest units (1 USDC)
    principal = 1 * 10 ** USDC_DECIMALS

    profitable_results = []

    for symbol, info in TOKENS.items():
        # Quote USDC -> token
        first_quote = quote_swap(CHAIN_ID, USDC_ADDRESS, info["address"], principal)
        if first_quote is None:
            continue
        try:
            intermediate_amount = int(first_quote.get("toTokenAmount", 0))
        except Exception:
            continue
        if intermediate_amount <= 0:
            continue

        # Quote token -> USDC
        second_quote = quote_swap(CHAIN_ID, info["address"], USDC_ADDRESS, intermediate_amount)
        if second_quote is None:
            continue
        try:
            final_amount = int(second_quote.get("toTokenAmount", 0))
        except Exception:
            continue
        if final_amount <= 0:
            continue

        # Calculate percentage profit
        profit_percent = (final_amount - principal) / principal * 100.0
        if profit_percent >= threshold:
            profitable_results.append((symbol, profit_percent))

    # Prepare timestamp in PST/PDT (America/Vancouver)
    tz = pytz.timezone("America/Vancouver")
    now = datetime.datetime.now(tz)
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    if profitable_results:
        lines = [f"{symbol}: {profit:.2f}%" for symbol, profit in profitable_results]
        message = (
            f"\u2B50\uFE0F Oportunidades de arbitragem encontradas\n"
            f"{timestamp_str}\n"
            + "\n".join(lines)
        )
    else:
        message = (
            f"\u2139\uFE0F Nenhuma arbitragem acima de {threshold:.2f}% no momento.\n"
            f"{timestamp_str}"
        )

    send_telegram_message(token, chat_id, message)


if __name__ == "__main__":
    perform_arbitrage_check()