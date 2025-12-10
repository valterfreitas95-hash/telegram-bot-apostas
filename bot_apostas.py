import os
import sys
import time
import datetime
import requests
from urllib.parse import urlparse
from telegram import Bot

# =====================================
# LENDO VARIÁVEIS DE AMBIENTE
# =====================================

# Lê o token do bot (e já tira espaços em branco)
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()

# Tenta ler CHAT_ID de duas formas possíveis
CHAT_ID = (os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()

# URL da API de jogos
API_URL_JOGOS = (os.getenv("API_URL_JOGOS") or "").strip()

# DEBUG: MOSTRA O QUE FOI LIDO
print("=== DEBUG VARIÁVEIS DE AMBIENTE ===")
print(f"TELEGRAM_TOKEN len={len(TELEGRAM_TOKEN)} valor='{TELEGRAM_TOKEN}'")
print(f"CHAT_ID='{CHAT_ID}'")
print(f"API_URL_JOGOS='{API_URL_JOGOS}'")
print("===================================")

# VALIDAÇÃO DO TOKEN
if not TELEGRAM_TOKEN:
    print("ERRO FATAL: TELEGRAM_TOKEN NÃO ENCONTRADO NO AMBIENTE DO RENDER.")
    print("→ Crie/ajuste a variável TELEGRAM_TOKEN em Environment e redeploy.")
    sys.exit(1)

if ":" not in TELEGRAM_TOKEN or not TELEGRAM_TOKEN.split(":")[0].isdigit():
    print("ERRO FATAL: TELEGRAM_TOKEN COM FORMATO INVÁLIDO.")
    print("→ Ele deve ser algo como '123456789:AAAAA...'.")
    sys.exit(1)

# VALIDAÇÃO DO CHAT_ID
if not CHAT_ID:
    print("⚠️ AVISO: CHAT_ID não configurado (CHAT_ID ou TELEGRAM_CHAT_ID).")
    print("→ Mensagens para o Telegram vão falhar ao enviar.")
else:
    print("✅ CHAT_ID encontrado.")

# VALIDAÇÃO DA API_URL_JOGOS
if not API_URL_JOGOS:
    print("ERRO FATAL: API_URL_JOGOS não configurada nas variáveis de ambiente.")
    print("→ Crie/ajuste a variável API_URL_JOGOS em Environment e redeploy.")
    sys.exit(1)

# Confere se a URL parece válida (tem esquema e host)
parsed = urlparse(API_URL_JOGOS)
if not parsed.scheme or not parsed.netloc:
    print("ERRO FATAL: API_URL_JOGOS parece inválida:")
    print(f"Valor atual: '{API_URL_JOGOS}'")
    print("→ Ela deve ser algo como 'https://meu-servidor.com/algum-endpoint'")
    sys.exit(1)

print("✅ API_URL_JOGOS parece válida.")

# Agora podemos criar o bot com segurança
bot = Bot(token=TELEGRAM_TOKEN)


# =====================================
# FUNÇÕES AUXILIARES
# =====================================

def data_hoje_str():
    hoje = datetime.datetime.now()
    return hoje.strftime("%Y-%m-%d")


def buscar_jogos_do_dia(data_str: str):
    """
    Busca todos os jogos do dia em TODAS as ligas disponíveis na API.
    A URL base deve estar em API_URL_JOGOS.
    """
    url = f"{API_URL_JOGOS}?date={data_str}"
    print(f"\n🔎 Buscando TODOS os jogos do dia {data_str} em todas as ligas:")
    print(f"URL chamada: {url}")

    try:
        resposta = requests.get(url, timeout=20)
        resposta.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("❌ Erro ao conectar na API de jogos:")
        print(e)
        return []

    try:
        dados = resposta.json()
    except ValueError:
        print("❌ Erro ao decodificar JSON da resposta da API.")
        return []

    jogos = []

    for jogo in dados:
        home = jogo.get("home_team") or jogo.get("home") or "Time da Casa"
        away = jogo.get("away_team") or jogo.get("away") or "Time Visitante"
        horario = jogo.get("commence_time") or jogo.get("time") or "Horário não informado"
        liga = jogo.get("league") or jogo.get("liga") or "Liga não informada"
        odd_casa = (
            jogo.get("odd_casa")
            or jogo.get("home_price")
            or jogo.get("odd")
            or "-"
        )

        jogos.append(
            {
                "home": home,
                "away": away,
                "horario": horario,
                "liga": liga,
                "odd_casa": odd_casa,
            }
        )

    print(f"✅ Total de jogos encontrados para {data_str}: {len(jogos)}")
    return jogos


def formatar_mensagem_jogos(jogos, data_str: str):
    if not jogos:
        return (
            f"⚠️ Não encontrei jogos para o dia *{data_str}* "
            f"ou a API não retornou resultados no momento."
        )

    texto = f"📅 *Jogos do dia {data_str}*\n"
    texto += "🔁 Considerando TODAS as ligas disponíveis na API.\n\n"

    for i, jogo in enumerate(jogos, start=1):
        texto += (
            f"{i}. {jogo['home']} x {jogo['away']}\n"
            f"🏆 Liga: {jogo['liga']}\n"
            f"🕒 Horário: {jogo['horario']}\n"
            f"💰 Odd casa (se disponível): {jogo['odd_casa']}\n\n"
        )

    return texto


def rodar_bot_uma_vez():
    print("\n🚀 BOT INICIADO (execução única)\n")

    data_str = data_hoje_str()
    print(f"📅 Buscando jogos do dia: {data_str}")

    jogos = buscar_jogos_do_dia(data_str)
    msg = formatar_mensagem_jogos(jogos, data_str)

    if not CHAT_ID:
        print("❌ Não foi possível enviar a mensagem: CHAT_ID não configurado.")
        return

    try:
        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        print("\n📤 Mensagem enviada ao Telegram com sucesso!")
    except Exception as e:
        print("❌ Erro ao enviar mensagem para o Telegram:")
        print(e)


if __name__ == "__main__":
    while True:
        try:
            rodar_bot_uma_vez()
        except Exception as e:
            print("❌ Erro inesperado no loop principal do bot:")
            print(e)

        print("⏳ Aguardando 1 hora para a próxima execução...\n")
        time.sleep(3600)
