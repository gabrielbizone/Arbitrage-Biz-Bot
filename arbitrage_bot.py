#!/usr/bin/env python3
# coding: utf-8

"""
arbitrage_bot_corrected.py
--------------------------

This script performs simple triangular arbitrage checks on the Polygon network
for USDC‑based pairs.  It works by quoting a swap from USDC into a target
token using the 1inch v4 API, then quoting a swap back from that token into
USDC.  If the return amount exceeds the original input by more than a
configurable percentage threshold, the bot will send an alert via Telegram
and optionally log the opportunity to a Google Sheet.

Environment variables used:

```
TELEGRAM_TOKEN             # Bot token obtained from BotFather on Telegram
TELEGRAM_CHAT_ID           # The chat ID or group ID to send notifications to
PROFIT_THRESHOLD_PERCENT   # Minimum percentage gain required to send an alert (float)

# Optional, only required if you want to log to Google Sheets
GOOGLE_SERVICE_ACCOUNT_JSON  # JSON credentials for a Google Service Account
GOOGLE_SHEET_ID              # ID of a Google Sheet where data will be appended
```

The token addresses used in this script are for Polygon (chain ID 137).
You can add or modify tokens in the TOKENS dictionary below.  Make sure
the contract addresses correspond to ERC‑20 tokens on Polygon.

Note: network calls are made to external APIs (1inch and Telegram).  If
these services are unavailable or rate‑limited, the script may fail.  You
should run this script in an environment with internet access.
"""

import os
import json
import time
import datetime
from typing import Dict, Optional

import requests

try:
    import pytz  # type: ignore
except ImportError:
    pytz = None  # gspread and pytz are optional; the script will run without them

try:
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore
except ImportError:
    gspread = None  # gspread will only be used if it's available and credentials are provided


# Constants
POLYGON_CHAIN_ID = 137
# USDC on Polygon (6 decimals)
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Dictionary of target tokens for arbitrage.  You can add additional
# tokens here or modify the addresses as needed.  All addresses should
# be checksummed Ethereum addresses on Polygon.
TOKENS: Dict[str, str] = {
    # token symbol : contract address on Polygon
    "LINK": "0x53e0bca35ec356bd5dddfebbd1fc0fbd03fae4c6",  # ChainLink
    "AAVE": "0xd6df932a45c0f255f85145f286ea0b2928b27c9c",  # Aave (AAVE)
    # Add more tokens as desired.  The user can customize this list.
    "MATIC": "0x0000000000000000000000000000000000001010",  # Wrapped MATIC (native token)
    "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",  # Wrapped Ether
    "WBTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",  # Wrapped Bitcoin
    "CRV": "0x172370d5Cd63279eFa6d502DAB29171933a610AF",  # Curve DAO Token
    "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",  # DAI stablecoin
    "XSGD": "0x009e056461d20350d8fC3e88f5A71325A1E6B7E4",  # xSGD (example address)
}



def get_telegram_credentials() -> Optional[tuple[str, str]]:
    """Retrieve Telegram credentials from environment variables.

    Returns
    -------
    Optional[tuple[str, str]]
        A tuple of (token, chat_id) if both are provided, otherwise None.
    """
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        return token, chat_id
    return None


def get_profit_threshold() -> float:
    """Return the profit threshold percentage from environment variables.

    Returns
    -------
    float
        Profit threshold (percent).  Defaults to 1.0 if not set or invalid.
    """
    default_threshold = 1.0
    value = os.environ.get("PROFIT_THRESHOLD_PERCENT")
    try:
        return float(value) if value is not None else default_threshold
    except ValueError:
        return default_threshold


def quote_swap(chain_id: int, from_addr: str, to_addr: str, amount: int) -> dict:
    """Quote a token swap using the 1inch v4 API.

    Parameters
    ----------
    chain_id : int
        The chain ID for the query (137 for Polygon).
    from_addr : str
        Address of the token you are swapping from.
    to_addr : str
        Address of the token you are swapping to.
    amount : int
        Amount of tokens to swap, in the smallest unit (wei or the token's decimals).

    Returns
    -------
    dict
        JSON response from the 1inch API.
    """
    url = f"https://api.1inch.io/v4.0/{chain_id}/quote"
    params = {
    try:
        # Perform the GET request with a timeout.  Any RequestException (e.g.,
        # ConnectionError, Timeout, HTTPError) will be caught below and
        # handled gracefully.
        response = requests.get(url, params=params, timeout=15)
        # If the response has an HTTP error status (4xx or 5xx), raise it
        response.raise_for_status()
        try:
            # Attempt to parse the response as JSON.  Some providers may
            # return HTML or other non‑JSON content when rate limited or
            # unavailable, which will cause json() to raise a ValueError.
            return response.json()
        except ValueError:
            # Return None to signal that parsing failed; the caller can decide
            # how to handle a missing response (e.g., skip this token).
            return None
    except requests.RequestException as err:
        # Catch network‑related errors (timeout, connection issues, HTTP errors)
        # and return None so that the caller can skip this token.  We log
        # the exception here for debugging purposes.
        print(f"Network error during quote: {err}")
        return None
n: str, chat_id: str, message: str) -> None:
    """Send a notification via Telegram bot.

    Parameters
    ----------
    token : str
        Telegram bot token.
    chat_id : str
        Target chat ID or group ID.
    message : str
        The message to send.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        # Log error but don't stop execution
        print(f"Failed to send Telegram message: {e}")


def append_to_sheet(service_account_json: str, sheet_id: str, row: list[str]) -> None:
    """Append a row of data to a Google Sheet.

    This function uses a service account to authenticate and append data.
    If gspread or google-auth is not installed, the function will simply return.

    Parameters
    ----------
    service_account_json : str
        JSON string with the service account credentials.
    sheet_id : str
        ID of the Google Sheet to append to.
    row : list[str]
        Row of data to append (each element becomes a cell).
    """
    if gspread is None or Credentials is None:
        print("gspread not available; skipping sheet append")
        return
    try:
        creds_info = json.loads(service_account_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        sheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"Failed to append data to Google Sheet: {e}")


def perform_arbitrage_check() -> None:
    """Check each token for arbitrage opportunities and send alerts if found."""
    telegram_creds = get_telegram_credentials()
    threshold = get_profit_threshold()
    service_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")

    # Use current timestamp in PST (or fallback to UTC if pytz is not available)
    tz_name = "America/Vancouver"
    now = datetime.datetime.now(pytz.timezone(tz_name)) if pytz else datetime.datetime.utcnow()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    # We quote 1 USDC (1e6 units) by default.  You can increase this amount
    amount_usdc = 10 ** 6  # 1 USDC in base units (6 decimals)

    for symbol, token_addr in TOKENS.items():
        try:
            # Step 1: USDC -> token
            quote1 = quote_swap(POLYGON_CHAIN_ID, USDC_ADDRESS, token_addr, amount_usdc)
            token_decimals = int(quote1["toToken"]["decimals"])
            # toTokenAmount is a string representing the raw amount (no decimals)
            to_amount_raw = int(quote1["toTokenAmount"])

            # Step 2: token -> USDC
            quote2 = quote_swap(POLYGON_CHAIN_ID, token_addr, USDC_ADDRESS, to_amount_raw)
            final_amount_usdc = int(quote2["toTokenAmount"])

            # Calculate profit percentage
            profit_percent = (final_amount_usdc - amount_usdc) / amount_usdc * 100.0

            if profit_percent >= threshold:
                message = (
                    f"⚡️ Triangular arbitrage opportunity detected!\n"
                    f"Route: USDC → {symbol} → USDC\n"
                    f"Estimated profit: {profit_percent:.2f}% for 1 USDC\n"
                    f"Detected at {timestamp_str}"
                )
                print(message)
                # Send Telegram alert if credentials are provided
                if telegram_creds:
                    send_telegram_message(telegram_creds[0], telegram_creds[1], message)
                # Append to Google Sheet if credentials are provided
                if service_json and sheet_id:
                    append_to_sheet(service_json, sheet_id, [timestamp_str, symbol, f"{profit_percent:.4f}"])
        except requests.HTTPError as http_err:
            print(f"HTTP error while quoting {symbol}: {http_err}")
        except Exception as e:
            print(f"Unexpected error while processing {symbol}: {e}")


def main() -> None:
    """Entry point for the script."""
    perform_arbitrage_check()


if __name__ == "__main__":
    main()
