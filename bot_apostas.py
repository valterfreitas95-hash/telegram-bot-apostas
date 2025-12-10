import os
import time
import threading
import datetime
import requests
from math import isfinite
from flask import Flask

# ==============================
# VARIÁVEIS DE AMBIENTE
# ==============================

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
CHAT_ID = (os.getenv("CHAT_ID") or "").strip()
ODDS_API_KEY = (os.getenv("ODDS_API_KEY") or "").strip()

MAX_ODD = float(os.getenv("MAX_ODD", "1.40"))   # limite de odd da casa
MIN_PROB = float(os.getenv("MIN_PROB", "0.70")) # 70% = 0.70

if not TELEGRAM_TOKEN:
    raise SystemExit("FALTA TELEGRAM_TOKEN no ambiente.")

if not CHAT_ID:
    raise SystemExit("FALTA CHAT_ID no ambiente.")

if not ODDS_API_KEY:
    raise SystemExit("FALTA ODDS_API_KEY (sua chave da The Odds API).")

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/upcoming/odds"

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
    print("📨 Enviando mensagem ao Telegram...")  # DEBUG

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
        except:
            pass

        try:
            print("Resposta:", resp.text)
        except Exception:
            pass

# ==============================
# MODELO C - FUNÇÕES
# ==============================

def agora_brasil():
    tz = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(tz)

def formatar_horario_iso(iso_str: str) -> str:
    try:
        if iso_str.endswith("Z"):
            iso_str = iso_str.replace("Z", "+00:00")
        dt_utc = datetime.datetime.fromisoformat(iso_str)
        tz_brasil = datetime.timezone(datetime.timedelta(hours=-3))
        dt_br = dt_utc.astimezone(tz_brasil)
        return dt_br.strftime("%d/%m %H:%M")
    except Exception:
        return iso_str

def buscar_jogos_modelo_c():
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }

    print("\n🔎 Chamando The Odds API (Modelo C)...")
    try:
        resp = requests.get(ODDS_API_URL, params=params, timeout=25)
        resp.raise_for_status()
        jogos_brutos = resp.json()
    except Exception as e:
        print("❌ Erro ao chamar a The Odds API:", e)
        return []

    selecionados = []

    for evento in jogos_brutos:
        try:
            home_team = evento.get("home_team") or "Time da casa"
            away_team = evento.get("away_team") or "Time visitante"
            liga = evento.get("sport_title") or evento.get("sport_key") or "Liga não informada"
            commence_time = evento.get("commence_time", "")

            bookmakers = evento.get("bookmakers") or []
            if not bookmakers:
                continue

            bk = bookmakers[0]
            casa_apostas = bk.get("title", "Casa não informada")

            markets = bk.get("markets") or []
            mercado_h2h = None
            for m in markets:
                if m.get("key") == "h2h":
                    mercado_h2h = m
                    break

            if not mercado_h2h:
                continue

            outcomes = mercado_h2h.get("outcomes") or []
            odd_casa = None
            for o in outcomes:
                if o.get("name") == home_team:
                    odd_casa = float(o.get("price"))
                    break

            if not odd_casa or not isfinite(odd_casa):
                continue

            prob_impl = 1.0 / odd_casa

            if odd_casa <= MAX_ODD or prob_impl >= MIN_PROB:
                selecionados.append({
                    "home": home_team,
                    "away": away_team,
                    "liga": liga,
                    "horario": commence_time,
                    "odd": odd_casa,
                    "prob": prob_impl,
                    "casa_apostas": casa_apostas,
                })

        except Exception as e:
            print("⚠️ Erro ao processar um evento:", e)
            continue

    selecionados.sort(key=lambda j: j["horario"])
    print(f"✅ Jogos selecionados pelo Modelo C: {len(selecionados)}")
    return selecionados

def montar_mensagem_modelo_c(jogos):
    if not jogos:
        hoje = agora_brasil().strftime("%d/%m/%Y")
        return (
            f"📊 *Apostas promissoras do dia (Modelo C)*\n\n"
            f"⚠️ Nenhum jogo encontrado dentro dos critérios para hoje ({hoje}).\n"
            f"Critérios: odd casa ≤ {MAX_ODD:.2f} ou prob. implícita ≥ {MIN_PROB*100:.0f}%."
        )

    hoje = agora_brasil().strftime("%d/%m/%Y")
    texto = f"📊 *Apostas promissoras do dia (Modelo C)*\n"
    texto += f"📅 Referência: {hoje}\n"
    texto += f"🎯 Critérios: odd casa ≤ {MAX_ODD:.2f} OU prob. ≥ {MIN_PROB*100:.0f}%\n\n"

    for i, j in enumerate(jogos, start=1):
        horario_fmt = formatar_horario_iso(j["horario"])
        prob_pct = j["prob"] * 100
        texto += (
            f"{i}. {j['home']} x {j['away']}\n"
            f"➡️ Sugestão: {j['home']} vencer\n"
            f"🏆 Liga: {j['liga']}\n"
            f"🕒 Horário: {horario_fmt}\n"
            f"💰 Odd: {j['odd']:.2f}\n"
            f"📈 Prob. implícita: {prob_pct:.1f}%\n"
            f"🏦 Casa: {j['casa_apostas']}\n\n"
        )

    return texto

def executar_modelo_c_uma_vez():
    print("\n🚀 Rodando Modelo C...")
    jogos = buscar_jogos_modelo_c()
    msg = montar_mensagem_modelo_c(jogos)
    enviar_telegram(msg)

def loop_trabalho():
    while True:
        try:
            executar_modelo_c_uma_vez()
        except Exception as e:
            print("❌ Erro inesperado no loop de trabalho:", e)
        print("⏳ Aguardando 1 hora para próxima execução...\n")
        time.sleep(3600)

# ==============================
# FLASK PARA O RENDER
# ==============================

app = Flask(__name__)

@app.route("/")
def index():
    return "OK - Bot de apostas (Modelo C) rodando.", 200

def iniciar_loop_em_thread():
    t = threading.Thread(target=loop_trabalho, daemon=True)
    t.start()

if __name__ == "__main__":
    iniciar_loop_em_thread()
    port = int(os.getenv("PORT", "10000"))
    print(f"🌐 Subindo servidor Flask na porta {port}...")
    app.run(host="0.0.0.0", port=port)
