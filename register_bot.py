#!/usr/bin/env python3
import os, sys, requests, json

"""
Registra o bot (Ana Lis) no Bitrix, apontando eventos para a URL pública.
Uso:
  export BITRIX_WEBHOOK="https://SEU_DOMINIO/rest/1/TOKEN"
  python register_bot.py
"""

def main():
    base = os.getenv("BITRIX_WEBHOOK", "https://laboratoriocac.bitrix24.com.br/rest/1/jvlko7nqb9mo0lo0/")
    public_url = os.getenv("PUBLIC_URL", "https://lis-v2-bot.onrender.com")
    if not base:
        print("Erro: defina BITRIX_WEBHOOK")
        sys.exit(1)

    body = {
        "CODE": "ana_lis_lab_cac",
        "TYPE": "B",
        "EVENT_MESSAGE_ADD": f"{public_url}/handler",
        "EVENT_WELCOME_MESSAGE": f"{public_url}/handler",
        "OPENLINE": "N",
        "PROPERTIES": {
            "NAME": "Ana Lis - Agente IA",
            "COLOR": "ORANGE",
            "EMAIL": "ana.lis@labcac.com.br",
            "WORK_POSITION": "Assistente IA do Lab CAC"
        }
    }
    url = f"{base}/imbot.register"
    r = requests.post(url, json=body, timeout=20)
    print("Status:", r.status_code)
    print("Resposta:", r.text)

if __name__ == "__main__":
    main()
