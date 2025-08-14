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
WEBHOOK_KEY = "jvlko7nqb9mo0lo0"  # Substitua pela sua chave real
BITRIX_WEBHOOK = f"https://laboratoriocac.bitrix24.com.br/rest/1/{WEBHOOK_KEY}"

@app.route('/install', methods=['POST'])
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
        "CLIENT_ID": "1",
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
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        print("📨 Dados recebidos no /handler:", data)

        mensagem_usuario = data.get("data[PARAMS][MESSAGE]", "")
        dialog_id = data.get("data[PARAMS][DIALOG_ID]")

        if not dialog_id:
            return jsonify({"status": "Diálogo ausente"})

        # ⏰ Restrição de horário (se ativado)
        if HABILITAR_RESTRICAO_HORARIO:
            hora = datetime.now().hour
            minuto = datetime.now().minute
            if hora < 6 or (hora == 6 and minuto < 30) or hora >= 23:
                mensagem_limite = "Ana Lis está disponível das 06:30 às 18:00. Por favor, retorne nesse horário 😊"
                requests.post(
                    f"{BITRIX_WEBHOOK}/imbot.message.add.json",
                    json={
                        "DIALOG_ID": dialog_id,
                        "CLIENT_ID": "8",
                        "MESSAGE": mensagem_limite
                    },
                    headers={"Content-Type": "application/json"}
                )
                return jsonify({"status": "Fora do horário, resposta enviada."})

        # 📎 Detecta arquivos enviados
        arquivo_url = None
        arquivo_nome = None

        for key, value in data.items():
            if key.endswith("][urlDownload]") and "data[PARAMS][FILES][" in key:
                arquivo_url = value
                inicio = key.find("FILES[") + 6
                fim = key.find("]", inicio)
                file_id = key[inicio:fim]
                arquivo_nome = data.get(f"data[PARAMS][FILES][{file_id}][name]", "arquivo_desconhecido")
                break

        # 🧠 Gera resposta da IA
        if arquivo_url and arquivo_nome:
            print("📂 Arquivo detectado! Enviando ao GPT-4o com visão...")
            try:
                resposta_ia = processar_arquivo_do_bitrix(arquivo_url, arquivo_nome)
            except Exception as e:
                print(f"❌ Erro em processar_arquivo_do_bitrix: {e}")
                resposta_ia = "❌ O tipo de arquivo não é reconhecido como imagem compatível para análise."
        elif mensagem_usuario:
            print("💬 Mensagem de texto detectada! Enviando ao GPT...")
            resposta_ia = chamar_openai_com(mensagem_usuario)
            resposta_ia = limpar_marcadores_de_citacao(resposta_ia)
        else:
            resposta_ia = "❗Mensagem vazia ou sem arquivo. Por favor, envie um texto ou anexo válido."

        # 📤 Envia resposta para o Bitrix
        requests.post(
            f"{BITRIX_WEBHOOK}/imbot.message.add.json",
            json={
                "DIALOG_ID": dialog_id,
                "CLIENT_ID": "8",
                "MESSAGE": resposta_ia
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
