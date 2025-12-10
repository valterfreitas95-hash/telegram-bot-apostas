import os
import time
import threading
import datetime
import requests
from math import isfinite
from flask import Flask

# =====================================================
# VARIÁVEIS DE AMBIENTE
# =====================================================

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
CHAT_ID = (os.getenv("CHAT_ID") or "").strip()
ODDS_API_KEY = (os.getenv("ODDS_API_KEY") or "").strip()

MAX_ODD = float(os.getenv("MAX_ODD", "1.40"))
MIN_PROB = float(os.getenv("MIN_PROB", "0.70"))

print("=== DEBUG VARIÁVEIS ===")
print("TELEGRAM_TOKEN len:", len(TELEGRAM_TOKEN))
print("CHAT_ID:", CHAT_ID)
print("ODDS_API_KEY len:", len(ODDS_API_KEY))
print("========================")

if not TELEGRAM_TOKEN:
    raise SystemExit("FALTA TELEGRAM_TOKEN no ambiente.")

if not CHAT_ID:
    raise SystemExit("FALTA CHAT_ID no ambiente.")

if not ODDS_API_KEY:
    raise SystemExit("FALTA ODDS_API_KEY no ambiente.")

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/upcoming/odds"


# =====================================================
# ENVIO AO TELEGRAM
# =====================================================

def enviar_telegram(msg: str):
    """Envia mensagem via API oficial do Telegram (rápida e estável)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }

    print("📨 Enviando mensagem ao Telegram...")

    try:
        r = requests.post(url, json=payload, timeout=15)
        print("📡 Status:", r.status_code)
        print("🧾 Resposta:", r.text)

        r.raise_for_status()
        print("📤 Mensagem enviada com sucesso!")

    except Exception as e:
        print("❌ Erro ao enviar mensagem:", e)


# =====================================================
# FUNÇÕES Modelo C
# =====================================================

def agora_brasil():
    tz = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(tz)


def formatar_horario(iso_str: str):
    try:
        if iso_str.endswith("Z"):
            iso_str = iso_str.replace("Z", "+00:00")
        dt_utc = datetime.datetime.fromisoformat(iso_str)
        br = dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-3)))
        return br.strftime("%d/%m %H:%M")
    except:
        return iso_str


def buscar_jogos_modelo_c():
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }

    print("\n🔎 Consultando The Odds API...")

    try:
        r = requests.get(ODDS_API_URL, params=params, timeout=20)
        r.raise_for_status()
        dados = r.json()
    except Exception as e:
        print("❌ Erro ao consultar Odds API:", e)
        return []

    selecionados = []

    for jogo in dados:
        try:
            home = jogo.get("home_team")
            away = jogo.get("away_team")
            liga = jogo.get("sport_title")
            horario = jogo.get("commence_time")

            if not jogo.get("bookmakers"):
                continue

            book = jogo["bookmakers"][0]
            market = None

            for m in book.get("markets", []):
                if m.get("key") == "h2h":
                    market = m
                    break

            if not market:
                continue

            outcomes = market.get("outcomes", [])
            odd_home = None

            for o in outcomes:
                if o.get("name") == home:
                    odd_home = float(o.get("price"))
                    break

            if not odd_home or not isfinite(odd_home):
                continue

            prob = 1 / odd_home

            if odd_home <= MAX_ODD or prob >= MIN_PROB:
                selecionados.append({
                    "home": home,
                    "away": away,
                    "liga": liga,
                    "horario": horario,
                    "odd": odd_home,
                    "prob": prob,
                    "casa": book.get("title", "Casa")
                })

        except:
            continue

    selecionados.sort(key=lambda j: j["horario"])
    print(f"✅ Jogos filtrados: {len(selecionados)}")
    return selecionados


def montar_mensagem(lista):
    hoje = agora_brasil().strftime("%d/%m/%Y")

    if not lista:
        return (
            f"📊 *Apostas promissoras do dia (Modelo C)*\n"
            f"📅 {hoje}\n\n"
            f"⚠️ Nenhum jogo atende os critérios hoje.\n"
        )

    msg = (
        f"📊 *Apostas promissoras do dia (Modelo C)*\n"
        f"📅 {hoje}\n"
        f"🎯 Critério: odd ≤ {MAX_ODD} ou prob ≥ {MIN_PROB*100:.0f}%\n\n"
    )

    for i, j in enumerate(lista, 1):
        msg += (
            f"{i}. *{j['home']}* x {j['away']}\n"
            f"🏆 Liga: {j['liga']}\n"
            f"🕒 Horário: {formatar_horario(j['horario'])}\n"
            f"💰 Odd: {j['odd']:.2f}\n"
            f"📈 Probabilidade: {j['prob']*100:.1f}%\n"
            f"🏦 Casa: {j['casa']}\n\n"
        )

    return msg


# =====================================================
# LOOP AUTOMÁTICO
# =====================================================

def executar():
    print("\n🚀 Executando Modelo C...")
    jogos = buscar_jogos_modelo_c()
    texto = montar_mensagem(jogos)
    enviar_telegram(texto)


def loop():
    while True:
        executar()
        print("⏳ Aguardando 1 hora...\n")
        time.sleep(3600)


# =====================================================
# FLASK PARA O RENDER
# =====================================================

app = Flask(__name__)

@app.route("/")
def index():
    return "BOT APOSTAS — MODELO C ONLINE", 200


def iniciar_thread():
    t = threading.Thread(target=loop, daemon=True)
    t.start()


if __name__ == "__main__":
    iniciar_thread()
    porta = int(os.getenv("PORT", "10000"))
    print(f"🌐 Flask rodando na porta {porta}...")
    app.run(host="0.0.0.0", port=porta)
