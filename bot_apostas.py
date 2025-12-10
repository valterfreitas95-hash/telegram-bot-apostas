import os
import time
import threading
import datetime
import requests
from flask import Flask

# ==============================
# VARIÁVEIS DE AMBIENTE
# ==============================

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
CHAT_ID = (os.getenv("CHAT_ID") or "").strip()

print("=== DEBUG VARIÁVEIS ===")
print("TELEGRAM_TOKEN len:", len(TELEGRAM_TOKEN))
print("CHAT_ID:", CHAT_ID)
print("========================")

if not TELEGRAM_TOKEN:
    raise SystemExit("FALTA TELEGRAM_TOKEN no ambiente.")

if not CHAT_ID:
    raise SystemExit("FALTA CHAT_ID no ambiente.")

# ==============================
# TELEGRAM (SEM BIBLIOTECA)
# ==============================

def enviar_telegram(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }
    print("📨 Enviando mensagem ao Telegram...")

    try:
        resp = requests.post(url, json=payload, timeout=20)
        print("📡 Código de resposta do Telegram:", resp.status_code)
        print("🧾 Corpo da resposta:", resp.text)

        resp.raise_for_status()
        print("📤 Mensagem enviada com sucesso ao Telegram.")

    except Exception as e:
        print("❌ Erro ao enviar mensagem para o Telegram:", e)
        try:
            print("Resposta do Telegram:", resp.text)
        except Exception:
            pass

# ==============================
# LOOP DE TRABALHO (TESTE)
# ==============================

def executar_teste():
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    print(f"\n🚀 Rodando TESTE DE ENVIO ({agora})...")
    msg = (
        "🧪 *Teste do bot de apostas*\n\n"
        f"Mensagem enviada em: {agora}\n"
        "Se você está lendo isso, o bot de envio para o Telegram está FUNCIONANDO ✅"
    )
    enviar_telegram(msg)

def loop_trabalho():
    while True:
        try:
            executar_teste()
        except Exception as e:
            print("❌ Erro inesperado no loop de trabalho:", e)
        print("⏳ Aguardando 1 hora para a próxima execução...\n")
        time.sleep(3600)

# ==============================
# FLASK PARA O RENDER
# ==============================

app = Flask(__name__)

@app.route("/")
def index():
    return "OK - Bot de apostas rodando (modo TESTE).", 200

def iniciar_loop_em_thread():
    t = threading.Thread(target=loop_trabalho, daemon=True)
    t.start()

if __name__ == "__main__":
    iniciar_loop_em_thread()
    port = int(os.getenv("PORT", "10000"))
    print(f"🌐 Subindo servidor Flask na porta {port}...")
    app.run(host="0.0.0.0", port=port)
