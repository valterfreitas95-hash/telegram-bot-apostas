import os
import time
import threading
import datetime
import requests
from math import isfinite
from flask import Flask
from telegram import Bot

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

bot = Bot(token=TELEGRAM_TOKEN)

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/upcoming/odds"

# ==============================
# FUNÇÕES AUXILIARES
# ==============================

def agora_brasil():
    tz = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(tz)

def formatar_horario_iso(iso_str: str) -> str:
    """
    Converte o 'commence_time' da API (UTC) para horário de Brasília (UTC-3)
    e devolve no formato DD/MM HH:MM.
    """
    try:
        # exemplo: "2025-12-10T20:00:00Z"
        if iso_str.endswith("Z"):
            iso_str = iso_str.replace("Z", "+00:00")
        dt_utc = datetime.datetime.fromisoformat(iso_str)
        tz_brasil = datetime.timezone(datetime.timedelta(hours=-3))
        dt_br = dt_utc.astimezone(tz_brasil)
        return dt_br.strftime("%d/%m %H:%M")
    except Exception:
        return iso_str  # se der erro, retorna cru mesmo

def buscar_jogos_modelo_c():
    """
    Busca jogos na The Odds API e aplica a lógica do Modelo C:
    - odd casa <= MAX_ODD OU prob implícita >= MIN_PROB
    """
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",     # Europa (geralmente melhor cobertura)
        "markets": "h2h",    # vencedor da partida
        "oddsFormat": "decimal"
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

            # pega o primeiro bookmaker
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
            # não deixa um erro em um jogo quebrar tudo
            print("⚠️ Erro ao processar um evento:", e)
            continue

    # ordena por horário
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

def enviar_modelo_c():
    print("\n🚀 Rodando Modelo C e enviando para o Telegram...")
    jogos = buscar_jogos_modelo_c()
    msg = montar_mensagem_modelo_c(jogos)

    try:
        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        print("📤 Mensagem enviada com sucesso!")
    except Exception as e:
        print("❌ Erro ao enviar mensagem para o Telegram:", e)

def loop_trabalho():
    """
    Loop em segundo plano:
    - roda o Modelo C
    - espera 1 hora
    """
    while True:
        try:
            enviar_modelo_c()
        except Exception as e:
            print("❌ Erro inesperado no loop de trabalho:", e)
        print("⏳ Aguardando 1 hora para próxima execução...\n")
        time.sleep(3600)

# ==============================
# FLASK PARA O RENDER (WEB SERVICE)
# ==============================

app = Flask(__name__)

@app.route("/")
def index():
    return "OK - Bot de apostas (Modelo C) rodando.", 200

def iniciar_loop_em_thread():
    t = threading.Thread(target=loop_trabalho, daemon=True)
    t.start()

if __name__ == "__main__":
    # inicia o loop em segundo plano
    iniciar_loop_em_thread()

    # sobe o servidor web para o Render ficar feliz 🙂
    port = int(os.getenv("PORT", "10000"))
    print(f"🌐 Subindo servidor Flask na porta {port}...")
    app.run(host="0.0.0.0", port=port)
