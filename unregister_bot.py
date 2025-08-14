#!/usr/bin/env python3
import os, sys, requests

"""
Remove o bot do módulo imbot.
Uso:
  export BITRIX_WEBHOOK="https://SEU_DOMINIO/rest/1/TOKEN"
  python unregister_bot.py <BOT_ID>
"""
def main():
    base = os.getenv("BITRIX_WEBHOOK", "https://laboratoriocac.bitrix24.com.br/rest/1/jvlko7nqb9mo0lo0/")
    if not base:
        print("Erro: defina BITRIX_WEBHOOK")
        sys.exit(1)
    if len(sys.argv) < 2:
        print("Uso: python unregister_bot.py <BOT_ID>")
        sys.exit(1)
    bot_id = sys.argv[1]
    url = f"{base}/imbot.unregister"
    resp = requests.post(url, data={"BOT_ID": bot_id}, timeout=20)
    print("Status:", resp.status_code)
    print("Resposta:", resp.text)

if __name__ == "__main__":
    main()
