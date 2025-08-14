import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime
from processar_arquivo import processar_arquivo_do_bitrix
from chamar_openai_com import chamar_openai_com  # Função separada
import re

def limpar_marcadores_de_citacao(resposta):
    # Remove blocos como ... ou ...
    resposta = re.sub(r"[].*?[]", "", resposta)
    # Remove caracteres soltos usados como marcador (ex: , , )
    return resposta.replace("", "").replace("", "").replace("", "")


app = Flask(__name__)

# ✅ Variável de controle de horário (desativa se False)
HABILITAR_RESTRICAO_HORARIO = False

# Configurações fixas
BOT_NAME = "Ana Lis"
BOT_COLOR = "ORANGE"
WELCOME_MESSAGE = "Olá! Sou a Ana Lis, sua assistente virtual. Como posso te ajudar?"

PUBLIC_URL = "https://lis-v2-bot.onrender.com"
WEBHOOK_KEY = "mhomlf8nwufnmyor"  # Substitua pela sua chave real
BITRIX_WEBHOOK = "https://laboratoriocac.bitrix24.com.br/rest/1/mhomlf8nwufnmyor/"

@app.route('/install', methods=['GET', 'POST'])
def install():
    data = request.args.to_dict()
    print("📦 Dados recebidos na instalação:", data)

    domain = data.get("DOMAIN")
    protocol = "https" if data.get("PROTOCOL") == "1" else "http"

    if not domain:
        return jsonify({"erro": "Domain não especificado", "status": "Erro interno"}), 500

    webhook_url = f"{protocol}://{domain}/rest/1/{WEBHOOK_KEY}/imbot.register.json"

    payload = {
        "CODE": "ana.lis.bot",
        "TYPE": "B",
        "EVENT_HANDLER": f"{PUBLIC_URL}/handler",
        "PROPERTIES": {
            "NAME": BOT_NAME,
            "COLOR": BOT_COLOR
        }
    }

    try:
        response = requests.post(webhook_url, json=payload)
        bitrix_result = response.json()
        print("🛰️ Resposta do Bitrix:", bitrix_result)
        return jsonify({"status": "Instalação recebida com sucesso", "bitrix_response": bitrix_result})
    except Exception as e:
        return jsonify({"erro": str(e), "status": "Erro interno"}), 500

@app.route('/handler', methods=['POST'])
def handler():
    try:
        data = request.get_json(force=True)
        print("📨 Dados recebidos no /handler:", json.dumps(data, indent=2))

        params = data.get("PARAMS", {})
        mensagem_usuario = params.get("MESSAGE", "")
        dialog_id = params.get("DIALOG_ID")

        if not dialog_id:
            return jsonify({"status": "Diálogo ausente"})

        resposta = "Olá! A Ana Lis está ativa e funcionando corretamente. 😉"

        requests.post(
            f"{BITRIX_WEBHOOK}/imbot.message.add.json",
            json={
                "DIALOG_ID": dialog_id,
                "MESSAGE": resposta
            },
            headers={"Content-Type": "application/json"}
        )

        return jsonify({"status": "Mensagem processada com sucesso."})

    except Exception as e:
        print("❌ Erro no handler:", e)
        return jsonify({"erro": str(e), "status": "Erro ao processar mensagem"}), 500


@app.route("/", methods=["GET"])
def home():
    return "Ana Lis está online!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
