import os
import time
import threading
import datetime
import requests
from math import isfinite
from flask import Flask, request

# =====================================================
# VARIÁVEIS DE AMBIENTE
# =====================================================

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
CHAT_ID = (os.getenv("CHAT_ID") or "").strip()
ODDS_API_KEY = (os.getenv("ODDS_API_KEY") or "").strip()

# Critérios do Modelo C
MAX_ODD = float(os.getenv("MAX_ODD", "1.40"))
MIN_PROB = float(os.getenv("MIN_PROB", "0.70"))  # 0.70 = 70%

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

def enviar_telegram(msg: str, chat_id: str | int | None = None):
    """Envia mensagem via API oficial do Telegram."""
    if chat_id is None:
        chat_id = CHAT_ID

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown",
    }

    print(f"📨 Enviando mensagem ao Telegram (chat_id={chat_id})...")

    try:
        r = requests.post(url, json=payload, timeout=20)
        print("📡 Status:", r.status_code)
        print("🧾 Resposta:", r.text)
        r.raise_for_status()
        print("📤 Mensagem enviada com sucesso!")
    except Exception as e:
        print("❌ Erro ao enviar mensagem:", e)


# =====================================================
# FUNÇÕES DO MODELO C
# =====================================================

def agora_brasil():
    tz = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(tz)


def formatar_horario(iso_str: str):
    """Converte o ISO da API para horário do Brasil (dd/mm HH:MM)."""
    try:
        if iso_str.endswith("Z"):
            iso_str = iso_str.replace("Z", "+00:00")
        dt_utc = datetime.datetime.fromisoformat(iso_str)
        br = dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-3)))
        return br.strftime("%d/%m %H:%M")
    except Exception:
        return iso_str


def buscar_jogos_modelo_c():
    """Busca jogos na The Odds API e aplica os filtros do Modelo C."""
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }

    print("\n🔎 Consultando The Odds API...")

    try:
        r = requests.get(ODDS_API_URL, params=params, timeout=25)
        r.raise_for_status()
        dados = r.json()
    except Exception as e:
        print("❌ Erro ao consultar Odds API:", e)
        return []

    selecionados = []

    for jogo in dados:
        try:
            sport_key = jogo.get("sport_key") or ""
            sport_title = jogo.get("sport_title") or ""

            # ⚽ FILTRO: SÓ FUTEBOL
            if not (
                sport_key.startswith("soccer_")
                or "Soccer" in sport_title
                or "Football" in sport_title
            ):
                # Ignora basquete, tênis, etc.
                continue

            home = jogo.get("home_team")
            away = jogo.get("away_team")
            liga = sport_title or jogo.get("sport_key")
            horario = jogo.get("commence_time")

            bookmakers = jogo.get("bookmakers") or []
            if not bookmakers:
                continue

            book = bookmakers[0]
            markets = book.get("markets") or []

            market = None
            for m in markets:
                if m.get("key") == "h2h":
                    market = m
                    break

            if not market:
                continue

            outcomes = market.get("outcomes") or []
            odd_home = None

            for o in outcomes:
                if o.get("name") == home:
                    odd_home = float(o.get("price"))
                    break

            if not odd_home or not isfinite(odd_home):
                continue

            prob = 1.0 / odd_home

            # Critério do Modelo C
            if odd_home <= MAX_ODD or prob >= MIN_PROB:
                selecionados.append(
                    {
                        "home": home,
                        "away": away,
                        "liga": liga,
                        "horario": horario,
                        "odd": odd_home,
                        "prob": prob,
                        "casa": book.get("title", "Casa"),
                    }
                )

        except Exception as e:
            print("⚠️ Erro ao processar jogo:", e)
            continue

    selecionados.sort(key=lambda j: j["horario"])
    print(f"✅ Jogos filtrados (apenas futebol): {len(selecionados)}")
    return selecionados


def montar_mensagem(jogos):
    hoje = agora_brasil().strftime("%d/%m/%Y")

    if not jogos:
        return (
            f"📊 *Apostas promissoras do dia (Modelo C)*\n"
            f"📅 {hoje}\n\n"
            f"⚠️ Nenhum jogo de futebol atendeu aos critérios hoje.\n"
            f"🎯 Odd casa ≤ {MAX_ODD:.2f} ou prob ≥ {MIN_PROB*100:.0f}%."
        )

    msg = (
        f"📊 *Apostas promissoras do dia (Modelo C)*\n"
        f"📅 {hoje}\n"
        f"🎯 Critérios: odd casa ≤ {MAX_ODD:.2f} OU prob ≥ {MIN_PROB*100:.0f}%\n\n"
    )

    for i, j in enumerate(jogos, 1):
        msg += (
            f"{i}. *{j['home']}* x {j['away']}\n"
            f"🏆 Liga: {j['liga']}\n"
            f"🕒 Horário: {formatar_horario(j['horario'])}\n"
            f"💰 Odd casa: {j['odd']:.2f}\n"
            f"📈 Prob. implícita: {j['prob']*100:.1f}%\n"
            f"🏦 Casa: {j['casa']}\n\n"
        )

    return msg


# =====================================================
# LOOP AUTOMÁTICO
# =====================================================

def executar_modelo_c():
    print("\n🚀 Executando Modelo C (rodada completa)...")
    jogos = buscar_jogos_modelo_c()
    texto = montar_mensagem(jogos)
    enviar_telegram(texto)


def loop_automático():
    while True:
        try:
            executar_modelo_c()
        except Exception as e:
            print("❌ Erro inesperado no loop automático:", e)
        print("⏳ Aguardando 1 hora...\n")
        time.sleep(3600)


# =====================================================
# FLASK + WEBHOOK (/hoje)
# =====================================================

app = Flask(__name__)

@app.route("/")
def index():
    return "BOT Apostas — Modelo C ONLINE (com /hoje)", 200


@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    """Recebe mensagens do Telegram e responde a /hoje."""
    data = request.get_json(force=True, silent=True) or {}
    message = data.get("message") or data.get("edited_message") or {}

    chat = message.get("chat") or {}
    chat_id_in = chat.get("id")
    text = (message.get("text") or "").strip()

    print("📨 Webhook recebido:", data)

    # Garante que só responde ao seu chat
    if str(chat_id_in) != str(CHAT_ID):
        print("⚠️ Mensagem de outro chat, ignorando.")
        return "ok", 200

    if text.startswith("/hoje"):
        # Responde rápido algo e depois roda o Modelo C
        enviar_telegram("⏳ Buscando jogos de hoje (Modelo C)...", chat_id=chat_id_in)
        try:
            executar_modelo_c()
        except Exception as e:
            enviar_telegram(f"❌ Erro ao rodar Modelo C: {e}", chat_id=chat_id_in)

    return "ok", 200


def iniciar_thread():
    t = threading.Thread(target=loop_automático, daemon=True)
    t.start()


if __name__ == "__main__":
    iniciar_thread()
    porta = int(os.getenv("PORT", "10000"))
    print(f"🌐 Flask rodando na porta {porta}...")
    app.run(host="0.0.0.0", port=porta)
