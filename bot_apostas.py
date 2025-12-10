import os
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

print("Token len:", len(TELEGRAM_TOKEN))
print("Chat ID:", CHAT_ID)

if not TELEGRAM_TOKEN:
    raise SystemExit("Falta TELEGRAM_TOKEN no ambiente.")

if not CHAT_ID:
    raise SystemExit("Falta CHAT_ID no ambiente.")

def enviar():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "🚨 TESTE SIMPLES: o bot FUNCIONOU!",
    }

    print("Enviando...")
    r = requests.post(url, json=payload)
    print("Status:", r.status_code)
    print("Resposta:", r.text)

if __name__ == "__main__":
    enviar()
