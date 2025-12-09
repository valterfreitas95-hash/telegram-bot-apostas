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

# Se quiser deixar fixo no código, substitua as aspas pelos seus valores
TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    "8050775984:AAGHY52cHSLbp2Q71g_GtLfif9jIQJkC-s0",  # seu token
)
ODDS_API_KEY = os.getenv(
    "ODDS_API_KEY",
    "49885b2118d4019dd79add13adb938e1",  # sua API key
)

# Esportes/Ligas que o bot vai analisar (pode ajustar depois)
SPORT_KEYS = [
    "soccer_epl",                 # Premier League
    "soccer_spain_la_liga",       # La Liga
    "soccer_italy_serie_a",       # Série A Itália
    "soccer_uefa_champs_league",  # Champions League
]

# Região das casas de aposta (uk/us/eu/au)
ODDS_REGION = "uk"

# MODELO C: odd <= 1.40 OU probabilidade >= 70%
MAX_ODD = 1.40
MIN_PROB = 0.70

# Fuso horário (Maceió)
TZ = ZoneInfo("America/Maceio")


# ==========================
# FUNÇÃO PARA BUSCAR ODDS
# ==========================

def get_promising_bets():
    """
    Busca jogos na The Odds API e retorna uma lista de apostas promissoras
    seguindo o Modelo C: odd <= 1.40 ou prob >= 70%.
    """
    if not ODDS_API_KEY or ODDS_API_KEY.startswith("COLOQUE_SUA_API_KEY"):
        return []

    suggestions = []

    for sport in SPORT_KEYS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": ODDS_REGION,
            "markets": "h2h",   # moneyline/head-to-head
            "oddsFormat": "decimal",
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            # Se der erro nesse esporte, passa para o próximo
            continue

        for event in data:
            home = event.get("home_team")
            away = event.get("away_team")
            commence_str = event.get("commence_time")

            # Converte horário do jogo para fuso de Maceió
            try:
                kickoff_utc = datetime.fromisoformat(
                    commence_str.replace("Z", "+00:00")
                )
                kickoff_local = kickoff_utc.astimezone(TZ)
                kickoff_fmt = kickoff_local.strftime("%d/%m %H:%M")
            except Exception:
                kickoff_fmt = "horário indisponível"

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
                    outcomes = m.get("outcomes", [])
                    for o in outcomes:
                        name = o.get("name")
                        price = o.get("price")
                        if not isinstance(price, (int, float)):
                            continue

                        if name == home:
                            if best_home_odd is None or price < best_home_odd:
                                best_home_odd = price
                                best_home_book = book_name
                        elif name == away:
                            if best_away_odd is None or price < best_away_odd:
                                best_away_odd = price
                                best_away_book = book_name

            league = event.get("sport_title", sport)

            def maybe_add_pick(team_name, odd, book):
                if not odd:
                    return
                prob = 1.0 / odd
                if odd <= MAX_ODD or prob >= MIN_PROB:
                    suggestions.append({
                        "league": league,
                        "home": home,
                        "away": away,
                        "team_pick": team_name,
                        "odd": odd,
                        "prob": prob,
                        "book": book,
                        "kickoff": kickoff_fmt,
                    })

            maybe_add_pick(home, best_home_odd, best_home_book)
            maybe_add_pick(away, best_away_odd, best_away_book)

    # Ordena pela maior probabilidade (menor odd)
    suggestions.sort(key=lambda x: x["prob"], reverse=True)
    return suggestions


def format_bets_message(suggestions, limit=5):
    """
    Formata a mensagem em texto para enviar no Telegram.
    """
    if not suggestions:
        return (
            "Hoje não encontrei nenhuma aposta dentro dos critérios "
            "(odd ≤ 1.40 ou probabilidade ≥ 70%).\n\n"
            "_Pode ser falta de jogos nas ligas configuradas ou limite da API._"
        )

    picks = suggestions[:limit]
    lines = []
    lines.append("📊 *Apostas promissoras do dia* (Modelo C)\n")

    for i, p in enumerate(picks, start=1):
        prob_pct = p["prob"] * 100
        lines.append(
            f"*{i}. {p['home']} x {p['away']}*  \n"
            f"➡️ Sugestão: *{p['team_pick']}* vencer  \n"
            f"🏆 Liga: {p['league']}  \n"
            f"🕒 Horário: {p['kickoff']}  \n"
            f"💰 Odd: *{p['odd']:.2f}*  \n"
            f"📈 Prob. implícita: *{prob_pct:.1f}%*  \n"
            f"🏦 Casa: {p['book']}\n"
        )

    lines.append("_Filtros: odd ≤ 1.40 OU probabilidade ≥ 70%._")
    lines.append("_Bot automático by Valter_")
    return "\n".join(lines)


# ==========================
# HANDLERS
# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Olá! Eu sou o bot de *apostas promissoras do dia*.\n\n"
        "Uso o *Modelo C*: odd ≤ 1.40 _OU_ probabilidade implícita ≥ 70%.\n\n"
        "Comandos disponíveis:\n"
        "/hoje – Buscar apostas promissoras agora\n"
        "/assinar – Receber apostas todo dia às 10h (horário de Maceió)\n"
        "/cancelar – Parar de receber as apostas diárias\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def hoje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Buscando apostas promissoras do dia...")
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

    # Remove job antigo, se existir
    if context.job_queue:
        for job in context.job_queue.jobs():
            if job.chat_id == chat_id and job.name == f"daily_{chat_id}":
                job.schedule_removal()

    run_time = dtime(hour=10, minute=0, tzinfo=TZ)

    context.job_queue.run_daily(
        send_daily_bets,
        time=run_time,
        days=(0, 1, 2, 3, 4, 5, 6),
        chat_id=chat_id,
        name=f"daily_{chat_id}",
    )

    await update.message.reply_text(
        "✅ Assinatura ativada!\n"
        "Vou te enviar as apostas promissoras *todos os dias às 10h* (horário de Maceió).",
        parse_mode="Markdown",
    )


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    removed = False

    if context.job_queue:
        for job in context.job_queue.jobs():
            if job.chat_id == chat_id and job.name == f"daily_{chat_id}":
                job.schedule_removal()
                removed = True

    if removed:
        await update.message.reply_text("🚫 Assinatura diária cancelada.")
    else:
        await update.message.reply_text("Você não tinha assinatura ativa.")


# ==========================
# MAIN
# ==========================

def main():
    if not TELEGRAM_TOKEN:
        print("ERRO: TELEGRAM_TOKEN não configurado.")
        return

    app: Application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hoje", hoje))
    app.add_handler(CommandHandler("assinar", assinar))
    app.add_handler(CommandHandler("cancelar", cancelar))

    print("Bot iniciado. Aguardando mensagens...")
    app.run_polling()


if __name__ == "__main__":
    main()
