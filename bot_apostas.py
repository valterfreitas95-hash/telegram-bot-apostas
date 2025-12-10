import requests
import datetime
import time
import os
from telegram import Bot

# =====================================
# CONFIGURAÇÕES
# =====================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# URL base da sua API de jogos
# Aqui você adapta para a URL que já estava usando no seu projeto.
# A ideia é: essa API deve devolver TODOS os jogos do dia,
# de TODAS AS LIGAS disponíveis, sem filtro por escalão.
API_URL = os.getenv("API_URL_JOGOS")  # exemplo: "https://sua-api.com/jogos"

bot = Bot(token=TELEGRAM_TOKEN)


# =====================================
# FUNÇÃO AUXILIAR: DATA DE HOJE (AAAA-MM-DD)
# =====================================
def data_hoje_str():
    hoje = datetime.datetime.now()
    return hoje.strftime("%Y-%m-%d")


# =====================================
# BUSCAR TODOS OS JOGOS DO DIA
# - sem filtro de liga
# - sem filtro de escalão
# - apenas pela data
# =====================================
def buscar_jogos_do_dia(data_str: str):
    """
    Busca todos os jogos do dia em TODAS as ligas disponíveis na API.
    Pressupõe que sua API aceite um parâmetro de data, por exemplo ?date=AAAA-MM-DD
    e retorne uma lista de jogos em JSON.
    """

    # Monte a URL de acordo com a sua API.
    # Se sua API já recebe a data de outra forma, é só adaptar.
    url = f"{API_URL}?date={data_str}"
    print(f"\n🔎 Buscando TODOS os jogos do dia {data_str} em todas as ligas:")
    print(url)

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

    # Aqui eu assumo uma estrutura genérica de jogo.
    # Adapte os nomes dos campos conforme o JSON REAL da sua API.
    for jogo in dados:
        # Exemplo de campos esperados:
        # - jogo["home_team"]
        # - jogo["away_team"]
        # - jogo["commence_time"] ou jogo["time"]
        # - jogo["league"] / jogo["liga"] (opcional, só pra exibir)
        # - jogo["odd"] ou jogo["odds_casa"] (se quiser mostrar odds)

        home = jogo.get("home_team") or jogo.get("home") or "Time da Casa"
        away = jogo.get("away_team") or jogo.get("away") or "Time Visitante"
        horario = jogo.get("commence_time") or jogo.get("time") or "Horário não informado"
        liga = jogo.get("league") or jogo.get("liga") or "Liga não informada"

        # Se tiver odd da casa e você quiser exibir:
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


# =====================================
# FORMATAR MENSAGEM PARA TELEGRAM
# - Lista todos os jogos do dia
# - Mostra liga, horário, times e odd (se tiver)
# =====================================
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


# =====================================
# LOOP PRINCIPAL
# =====================================
def rodar_bot_uma_vez():
    print("\n🚀 BOT INICIADO (execução única)\n")

    data_str = data_hoje_str()
    print(f"📅 Buscando jogos do dia: {data_str}")

    jogos = buscar_jogos_do_dia(data_str)

    msg = formatar_mensagem_jogos(jogos, data_str)

    try:
        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        print("\n📤 Mensagem enviada ao Telegram com sucesso!")
    except Exception as e:
        print("❌ Erro ao enviar mensagem para o Telegram:")
        print(e)


# =====================================
# EXECUÇÃO CONTÍNUA (A CADA 1 HORA)
# Se quiser só 1 vez por dia, você pode remover o while True
# e chamar apenas rodar_bot_uma_vez()
# =====================================
if __name__ == "__main__":
    while True:
        try:
            rodar_bot_uma_vez()
        except Exception as e:
            print("❌ Erro inesperado no loop principal do bot:")
            print(e)

        # Espera 1 hora para rodar de novo
        print("⏳ Aguardando 1 hora para a próxima execução...\n")
        time.sleep(3600)
