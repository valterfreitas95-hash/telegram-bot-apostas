import os
import datetime
from typing import List, Dict, Any

import requests


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

# ⚠️ Configure essas variáveis no painel do Render (Environment):
# TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ODDS_API_URL, ODDS_API_KEY (se precisar)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

API_URL = os.getenv("ODDS_API_URL", "").strip()       # URL REAL da sua API de jogos
API_KEY = os.getenv("ODDS_API_KEY", "").strip()       # Se não usar key, pode deixar vazio


# ============================================================
# CONFIGURAÇÃO DE FILTRO (AQUI VOCÊ MANDA!)
# ============================================================

# 👉 Se quiser TODOS os jogos possíveis (sem limite de odd / probabilidade):
MAX_ODD = None       # None = sem limite máximo de odd
MIN_PROB = None      # None = sem limite mínimo de probabilidade implícita

# Exemplo se quiser voltar para "modelo seguro":
# MAX_ODD = 1.40
# MIN_PROB = 0.70  # 70%


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def validar_config() -> None:
    """Valida as configs básicas e gera erro claro se faltar algo importante."""
    if not TELEGRAM_BOT_TOKEN or "COLOQUE_SEU_TOKEN" in TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN não configurado. "
            "Defina o token real do bot nas variáveis de ambiente do Render."
        )

    if not TELEGRAM_CHAT_ID or "COLOQUE_SEU_CHAT_ID" in TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID não configurado. "
            "Defina o chat_id real nas variáveis de ambiente do Render."
        )

    if not API_URL:
        raise RuntimeError(
            "ODDS_API_URL não configurada. "
            "Defina nas variáveis de ambiente do Render a URL REAL da sua API de jogos "
            "(a mesma que você usava antes)."
        )


def calcular_probabilidade_implicita(odd: float) -> float:
    """
    Converte odd decimal em probabilidade implícita.
    Ex.: odd 1.40 -> ~0.714 (71.4%)
    """
    if odd is None or odd <= 0:
        return 0.0
    return 1.0 / odd


# ============================================================
# BUSCA DE JOGOS NA API (SEM ESCALÃO A/B)
# ============================================================

def buscar_todos_os_jogos(data: datetime.date) -> List[Dict[str, Any]]:
    """
    Busca TODOS os jogos possíveis na API, sem filtrar por escalão A/B.
    Você só precisa garantir que API_URL e parâmetros batem com sua API real.
    """
    data_str = data.strftime("%Y-%m-%d")

    params = {
        # Ajuste esses parâmetros conforme a sua API
        "date": data_str,
    }

    # Se sua API exige API_KEY no querystring (tipo ?api_key=...):
    if API_KEY:
        params["api_key"] = API_KEY

    # Chamada HTTP
    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()

    jogos = response.json()

    # Caso a API retorne algo do tipo {"data": [...]}:
    if isinstance(jogos, dict) and "data" in jogos:
        jogos = jogos["data"]

    if not isinstance(jogos, list):
        raise RuntimeError(
            f"A resposta da API não é uma lista. Resposta: {str(jogos)[:300]}"
        )

    return jogos


# ============================================================
# FILTRO DE JOGOS (AQUI TIRA ESCALÃO E LIMITE DE QUANTIDADE)
# ============================================================

def filtrar_jogos(jogos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aplica APENAS filtros de odd/probabilidade.
    NÃO filtra por liga, escalão A/B, país etc.
    NÃO limita a quantidade de jogos.
    """
    jogos_filtrados: List[Dict[str, Any]] = []

    for jogo in jogos:
        try:
            # ⚠️ IMPORTANTE:
            # Ajuste os nomes abaixo de acordo com os campos que sua API retorna.
            # Exemplos comuns:
            # - "home_team", "away_team", "league", "commence_time", "odd_home"
            # - "time_casa", "time_fora", "liga", "inicio", "odd_casa"
            odd_casa = jogo.get("home_odds") or jogo.get("odd_casa") or jogo.get("homePrice")
            if odd_casa is None:
                # se não tiver odd da casa, tenta a do favorito, etc.
                continue

            odd_casa = float(odd_casa)

            if odd_casa <= 1.01:
                # ignora odds absurdas ou inválidas
                continue

            prob_implicita = calcular_probabilidade_implicita(odd_casa)

            # ---------- FILTRO DE ODD ----------
            if MAX_ODD is not None and odd_casa > MAX_ODD:
                continue

            # ---------- FILTRO DE PROBABILIDADE ----------
            if MIN_PROB is not None and prob_implicita < MIN_PROB:
                continue

            # Se passou nos filtros, anexa dados calculados
            jogo["odd_base"] = odd_casa
            jogo["prob_implicita"] = prob_implicita

            jogos_filtrados.append(jogo)

        except Exception as e:
            print(f"[WARN] Erro ao processar jogo: {e} | Dados: {str(jogo)[:200]}")
            continue

    # NÃO limitar quantidade: nada de [:5] aqui
    return jogos_filtrados


# ============================================================
# FORMATAÇÃO DA MENSAGEM PARA O TELEGRAM
# ============================================================

def formatar_mensagem(jogos: List[Dict[str, Any]], data: datetime.date) -> str:
    """
    Monta a mensagem com todos os jogos filtrados.
    """
    data_str = data.strftime("%d/%m/%Y")

    if not jogos:
        return f"📊 Nenhum jogo encontrado para {data_str} com os filtros atuais."

    linhas: List[str] = []
    linhas.append(f"📊 Apostas do dia {data_str}")
    linhas.append("")

    # Se quiser, pode ordenar por probabilidade implícita (maior -> menor)
    jogos_ordenados = sorted(
        jogos,
        key=lambda j: j.get("prob_implicita", 0),
        reverse=True
    )

    for idx, jogo in enumerate(jogos_ordenados, start=1):
        # Ajuste os nomes conforme sua API
        casa = (
            jogo.get("home_team")
            or jogo.get("time_casa")
            or jogo.get("home")
            or "Time da Casa"
        )
        fora = (
            jogo.get("away_team")
            or jogo.get("time_fora")
            or jogo.get("away")
            or "Time Visitante"
        )
        liga = (
            jogo.get("league")
            or jogo.get("liga")
            or jogo.get("competition")
            or "Liga não informada"
        )

        # horário: pode vir como timestamp, string ISO, etc.
        horario = jogo.get("start_time") or jogo.get("inicio") or jogo.get("commence_time") or ""
        # se for algo tipo "2025-12-10T18:30:00Z", você pode simplificar depois

        odd_base = float(jogo.get("odd_base", 0))
        prob_imp = float(jogo.get("prob_implicita", 0)) * 100.0

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


# ============================================================
# ENVIO DA MENSAGEM PARA O TELEGRAM
# ============================================================

def enviar_para_telegram(texto: str) -> None:
    if not texto:
        print("[WARN] Texto vazio, nada enviado para Telegram.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        if not resp.ok:
            print("[ERRO] Falha ao enviar mensagem para o Telegram:", resp.text)
        else:
            print("[INFO] Mensagem enviada para o Telegram com sucesso.")
    except Exception as e:
        print(f"[ERRO] Exceção ao enviar mensagem para o Telegram: {e}")


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def main() -> None:
    validar_config()

    hoje = datetime.date.today()
    print(f"[INFO] Buscando todos os jogos de {hoje} ...")

    try:
        jogos_brutos = buscar_todos_os_jogos(hoje)
    except Exception as e:
        print(f"[ERRO] Falha ao buscar jogos na API: {e}")
        # Se quiser, também envia um aviso para você no Telegram:
        enviar_para_telegram(f"⚠️ Erro ao buscar jogos na API: {e}")
        return

    print(f"[INFO] Total de jogos retornados pela API: {len(jogos_brutos)}")

    jogos_filtrados = filtrar_jogos(jogos_brutos)
    print(f"[INFO] Total de jogos após filtros: {len(jogos_filtrados)}")

    mensagem = formatar_mensagem(jogos_filtrados, hoje)
    print("[INFO] Prévia da mensagem:\n", mensagem[:500], "...\n")

    enviar_para_telegram(mensagem)


if __name__ == "__main__":
    main()
