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
MAX_ODD = float(os.getenv("MAX_ODD", "1.40"))   # odd máxima da casa
MIN_PROB = float(os.getenv("MIN_PROB", "0.70")) # prob mínima (70%)

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
# TEXTOS PADRÃO
# =====================================================

WELCOME_TEXT = (
    "👋 Bem-vindo!\n\n"
    "Eu envio *apostas de HOJE* com *odd até 1.40*, misturando lig
