import requests
import datetime
import os
from typing import List, Dict, Any

# ==========================
# CONFIGURAÇÕES DO BOT
# ==========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "COLOQUE_SEU_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "COLOQUE_SEU_CHAT_ID_AQUI")

# Se você tiver uma API de odds, coloque aqui.
API_URL = "https://sua-api-de-jogos.com/matches"  # EXEMPLO, substitua pela sua
API_KEY = os.getenv("ODDS_API_KEY", "SUA_API_KEY_AQUI")

# ==========================
# CONFIGURAÇÃO DE FILTRO
# ==========================
# 🔴 AQUI É ONDE VOCÊ REALMENTE CONTROLA O FILTRO

# Se quiser TODOS os jogos possíveis, sem limite de odd, deixe assim:
MAX_ODD = None        # None = sem limite de odd (pega todas)
MIN_PROB = None       # None = sem limite de probabilidade (pega todas)

# Se quiser manter a lógica antiga (ex: até 1.40 ou >= 70% probabilidade),
# basta trocar aqui:
# MAX_ODD = 1.40
# MIN_PROB = 0.70     # 70%


# ==========================
# BUSCA DE JOGOS NA API
# ==========================

def buscar_todos_os_jogos(data: datetime.date) -> List[Dict[str, Any]]:
    """
    Esta função deve buscar TODOS os jogos possíveis na sua fonte de dados,
    sem filtrar por liga, escalão A/B etc.
    Adapte o formato de acordo com a API que você usa.
    """
    params = {
        "date": data.strftime("%Y-%m-%d"),
        "api_key": API_KEY,
        # importante: não filtrar por liga, divisão ou escalão aqui
    }

    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()

    # Aqui assumo que a API devolve uma lista de jogos em JSON
    jogos = response.json()
    return jogos


# ==========================
# FILTRO DE JOGOS (SEM ESCALÃO)
# ==========================

def calcular_probabilidade_implicita(odd: float) -> float:
    """
    Converte odd decimal em probabilidade implícita.
    Ex.: odd 1.40 -> ~71.4%
    """
    if odd <= 0:
        return 0.0
    return 1.0 / odd


def filtrar_jogos(jogos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aplica APENAS os filtros de odd/probabilidade, SEM filtrar ligas,
    SEM escalar A/B, SEM limitar quantidade de jogos.
    """
    jogos_filtrados = []

    for jogo in jogos:
        try:
            # Ajuste esses campos para bater com o retorno da sua API
            odd_casa = float(jogo.get("home_odds", 0))
            odd_empate = float(jogo.get("draw_odds", 0))
            odd_fora = float(jogo.get("away_odds", 0))

            # Exemplo: escolher a odd que você usa como base (vitória da casa, por exemplo)
            odd_base = odd_casa

            if odd_base <= 0:
                continue

            prob_implicita = calcular_probabilidade_implicita(odd_base)

            # ---------- FILTRO DE ODD ----------
            if MAX_ODD is not None and odd_base > MAX_ODD:
                continue

            # ---------- FILTRO DE PROBABILIDADE ----------
            if MIN_PROB is not None and prob_implicita < MIN_PROB:
                continue

            # Se passou nos filtros, adiciona o jogo
            jogo["odd_base"] = odd_base
            jogo["prob_implicita"] = prob_implicita
            jogos_filtrados.append(jogo)

        except Exception as e:
            # Se der erro em algum jogo específico, ignora ele
            print(f"Erro ao processar jogo: {e}")
            continue

    # IMPORTANTE: NÃO LIMITAR A QUANTIDADE AQUI
    # Nada de [:5], nada de contagem, deixa todos passarem
    return jogos_filtrados


# ==========================
# FORMATAÇÃO DA MENSAGEM
# ==========================

def formatar_mensagem(jogos: List[Dict[str, Any]], data: datetime.date) -> str:
    """
    Monta o texto que vai ser enviado para o Telegram.
    """
    if not jogos:
        return f"📊 Nenhum jogo encontrado para {data.strftime('%d/%m/%Y')} com os filtros atuais."

    linhas = []
    linhas.append(f"📊 Apostas do dia {data.strftime('%d/%m/%Y')}")
    linhas.append("")

    for idx, jogo in enumerate(jogos, start=1):
        casa = jogo.get("home_team", "Time da Casa")
        fora = jogo.get("away_team", "Time Visitante")
        liga = jogo.get("league", "Liga desconhecida")
        horario = jogo.get("start_time", "")  # formato string, ex: "18:30"

        odd_base = jogo.get("odd_base", 0)
        prob_imp = jogo.get("prob_implicita", 0) * 100  # em %

        bloco = (
            f"{idx}. {casa} x {fora}\n"
            f"➡️ Sugestão: Vitória do time da casa\n"
            f"🏆 Liga: {liga}\n"
            f"🕒 Horário: {horario}\n"
            f"💰 Odd: {odd_base:.2f}\n"
            f"📈 Prob. implícita: {prob_imp:.1f}%\n"
        )
        linhas.append(bloco)

    return "\n".join(linhas)


# ==========================
# ENVIO PARA TELEGRAM
# ==========================

def enviar_para_telegram(texto: str) -> None:
    """
    Envia mensagem de texto para o chat configurado no Telegram.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
    }

    resp = requests.post(url, json=payload, timeout=30)
    if not resp.ok:
        print("Erro ao enviar mensagem para o Telegram:", resp.text)


# ==========================
# FUNÇÃO PRINCIPAL
# ==========================

def main():
    # Exemplo: buscar jogos de HOJE
    hoje = datetime.date.today()

    print(f"Buscando todos os jogos de {hoje}...")
    jogos_brutos = buscar_todos_os_jogos(hoje)

    print(f"Total de jogos retornados pela API: {len(jogos_brutos)}")

    # AQUI NÃO TEM ESCALÃO A/B, NEM LIMITE DE QUANTIDADE
    jogos_filtrados = filtrar_jogos(jogos_brutos)

    print(f"Total de jogos após filtros: {len(jogos_filtrados)}")

    mensagem = formatar_mensagem(jogos_filtrados, hoje)
    enviar_para_telegram(mensagem)
    print("Mensagem enviada para o Telegram.")


if __name__ == "__main__":
    main()
