import os
import requests
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ==========================
# CONFIGURAÇÕES DO BOT
# ==========================

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    "8050775984:AAGHY52cHSLbp2Q71g_GtLfif9jIQJkC-s0"
)

ODDS_API_KEY = os.getenv(
    "ODDS_API_KEY",
    "49885b2118d4019dd79add13adb938e1"
)

# Escalão A – ligas grandes
SPORT_KEYS_TIER_A = [
    "soccer_epl",                  # Premier League
    "soccer_spain_la_liga",        # La Liga
    "soccer_italy_serie_a",        # Serie A
    "soccer_germany_bundesliga",   # Bundesliga
    "soccer_france_ligue_one",     # Ligue 1
    "soccer_uefa_champs_league",   # Champions League
]

# Escalão B – boas ligas para volume
SPORT_KEYS_TIER_B = [
    "soccer_brazil_campeonato",        # Brasileirão
    "soccer_argentina_primera_division",
    "soccer_netherlands_eredivisie",
    "soccer_turkey_super_league",
    "soccer_portugal_primeira_liga",
    "soccer_belgium_first_division_a",
    "soccer_usa_mls",
]

# Mistura tudo: Escalão A + Escalão B
SPORT_KEYS = SPORT_KEYS_TIER_A + SPORT_KEYS_TIER_B

# Região das casas de aposta
ODDS_REGION = "uk"

# Filtro de odd
MAX_ODD = 1.40

# Fuso horário
TZ = ZoneInfo("America/Maceio")


# ==========================
# BUSCA E FILTRO DE APOSTAS
# ==========================

def get_promising_bets():
    """
    Busca jogos na The Odds API e retorna apostas com odd <= 1.40
    SOMENTE para jogos de HOJE (no fuso de Maceió),
    misturando ligas de Escalão A e B.
    """
    if not ODDS_API_KEY:
        return []

    suggestions = []
    today = datetime.now(TZ).date()

    for sport in SPORT_KEYS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": ODDS_REGION,
            "markets": "h2h",
            "oddsFormat": "decimal",
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            # Se der erro nesse esporte, ignora e segue
            continue

        for event in data:
            home = event.get("home_team")
            away = event.get("away_team")
            commence_str = event.get("commence_time")

            # Conversão de horário
            try:
                kickoff_utc = datetime.fromisoformat(
                    commence_str.replace("Z", "+00:00")
                )
                kickoff_local = kickoff_utc.astimezone(TZ)
                kickoff_fmt = kickoff_local.strftime("%d/%m %H:%M")
            except Exception:
                kickoff_local = None
                kickoff_fmt = "horário indisponível"

            # 📌 FILTRA APENAS JOGOS DE HOJE
            if not kickoff_local or kickoff_local.date() != today:
                continue

            bookmakers = event.get("bookmakers", [])
            if not bookmakers:
                continue

            best_home_odd = None
            best_away_odd = None
            best_home_book = None
            best_away_book = None

            for b in bookmakers:
                book_name = b.get("title") or b.get("key")
                markets = b.get("markets", [])
                for m in markets:
                    if m.get("key") != "h2h":
                        continue
                    for o in m.get("outcomes", []):
                        team = o.get("name")
                        price = o.get("price")
                        if not isinstance(price, (int, float)):
                            continue

                        if team == home:
                            if best_home_odd is None or price < best_home_odd:
                                best_home_odd = price
                                best_home_book = book_name
                        elif team == away:
                            if best_away_odd is None or price < best_away_odd:
                                best_away_odd = price
                                best_away_book = book_name

            league = event.get("sport_title", sport)

            def maybe_add(team_name, odd, book):
                if not odd:
                    return
                # 📌 Filtro: somente odds até 1.40
                if odd <= MAX_ODD:
                    suggestions.append({
                        "league": league,
                        "home": home,
                        "away": away,
                        "team_pick": team_name,
                        "odd": odd,
                        "book": book,
                        "kickoff": kickoff_fmt,
                    })

            maybe_add(home, best_home_odd, best_home_book)
            maybe_add(away, best_away_odd, best_away_book)

    # 📌 Ordena pelas MAIORES odds dentro do limite (mais perto de 1.40)
    suggestions.sort(key=lambda x: x["odd"], reverse=True)

    return suggestions


# ==========================
# FORMATAÇÃO DE TEXTO
# ==========================

def format_bets_message(suggestions):
    """
    Formata a mensagem com TODAS as apostas encontradas.
    Sem limite de 5 – lista tudo em ordem, numerado.
    """
    if not suggestions:
        return (
            "Hoje não encontrei nenhuma aposta dentro do filtro (odd ≤ 1.40) "
            "nas ligas configuradas.\n"
            "_Pode ser falta de jogos hoje ou limite da API._"
        )

    lines = ["📊 *Apostas de Hoje* (odd ≤ 1.40)\n"]

    for i, p in enumerate(suggestions, 1):
        lines.append(
            f"*{i}. {p['home']} x {p['away']}*\n"
            f"➡️ Sugestão: *{p['team_pick']}* vencer\n"
            f"🏆 Liga: {p['league']}\n"
            f"🕒 Horário: {p['kickoff']}\n"
            f"💰 Odd: *{p['odd']:.2f}*\n"
            f"🏦 Casa: {p['book']}\n"
        )

    lines.append("_Filtro: somente odds até 1.40, misturando Escalão A e B._")
    lines.append("_Bot automático by Valter_")

    return "\n".join(lines)


# ==========================
# HANDLERS DO TELEGRAM
# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bem-vindo!\n\n"
        "Eu envio *apostas de HOJE* com *odd até 1.40*, "
        "misturando ligas de Escalão A e B para ter o maior número possível de jogos.\n\n"
        "Comandos:\n"
        "/hoje – Buscar apostas de hoje\n"
        "/assinar – Receber todo dia às 10h\n"
        "/cancelar – Parar envio diário\n"
    )


async def hoje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Buscando apostas de hoje...")
    suggestions = get_promising_bets()
    msg = format_bets_message(suggestions)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def send_daily_bets(context: ContextTypes.DEFAULT_TYPE):
    suggestions = get_promising_bets()
    msg = format_bets_message(suggestions)
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=msg,
        parse_mode="Markdown",
    )


async def assinar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # remove jobs antigos
    for job in context.job_queue.jobs():
        if job.chat_id == chat_id:
            job.schedule_removal()

    run_time = dtime(10, 0, tzinfo=TZ)

    context.job_queue.run_daily(
        send_daily_bets,
        time=run_time,
        days=(0, 1, 2, 3, 4, 5, 6),
        name=f"daily_{chat_id}",
        chat_id=chat_id,
    )

    await update.message.reply_text(
        "✅ Envio diário ativado! Vou mandar as apostas todo dia às 10h."
    )


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    removed = False

    for job in context.job_queue.jobs():
        if job.chat_id == chat_id:
            job.schedule_removal()
            removed = True

    if removed:
        await update.message.reply_text("🚫 Envios diários cancelados.")
    else:
        await update.message.reply_text("Você não tinha envio diário ativado.")


# ==========================
# MAIN
# ==========================

def main():
    app: Application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hoje", hoje))
    app.add_handler(CommandHandler("assinar", assinar))
    app.add_handler(CommandHandler("cancelar", cancelar))

    print("Bot iniciado. Aguardando mensagens...")
    app.run_polling()


if __name__ == "__main__":
    main()
