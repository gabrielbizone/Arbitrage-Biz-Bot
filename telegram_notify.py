
import os
import requests
import json

def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não configurados no ambiente.")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": str(text), "disable_web_page_preview": True},
            timeout=10,
        )
        data = r.json()
        if not data.get("ok"):
            print("⚠️ Falha ao enviar Telegram:", json.dumps(data))
        return bool(data.get("ok"))
    except Exception as e:
        print("⚠️ Erro ao enviar Telegram:", e)
        return False
