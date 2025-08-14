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
BOT_NAME = "Ana Lis - Agente IA - Agente IA"
BOT_COLOR = "ORANGE"
WELCOME_MESSAGE = "Olá! Sou a Ana Lis - Agente IA, sua assistente virtual. Como posso te ajudar?"

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
                mensagem_limite = "Ana Lis - Agente IA está disponível das 06:30 às 18:00. Por favor, retorne nesse horário 😊"
                requests.post(
                    f"{BITRIX_WEBHOOK}/imbot.message.add.json",
                    json={
                        "DIALOG_ID": dialog_id,
                        "CLIENT_ID": "50",
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
                "CLIENT_ID": "50",
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
    return "Ana Lis - Agente IA está online!"

# ====== Bitrix /handler (robusto: aceita JSON e x-www-form-urlencoded) ======
import logging
import re
logging.basicConfig(level=logging.INFO)

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK", "https://laboratoriocac.bitrix24.com.br/rest/1/jvlko7nqb9mo0lo0/")  # inbound com escopos imbot, im

def _flatten_form(form):
    d = {}
    try:
        lists = form.lists()
    except Exception:
        # Compat fallback
        lists = [(k, form.getlist(k)) for k in form.keys()]
    for k, v in lists:
        d[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
    return d

def _limpar_marcadores_de_citacao(resposta: str) -> str:
    resposta = re.sub(r"[].*?[]", "", resposta)
    return resposta.replace("", "").replace("", "").replace("", "")

@app.route("/handler", methods=["POST"])
def bitrix_handler():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            payload = _flatten_form(request.form)

        app.logger.info(f"[HANDLER] headers={dict(request.headers)}")
        app.logger.info(f"[HANDLER] payload={payload}")

        event = (payload.get("event") or payload.get("EVENT") or "").upper()
        # Eventos comuns: OnImBotMessageAdd, OnImBotJoinChat
        if event in ("ONIMBOTMESSAGEADD", "ONIMBOTJOINCHAT", "ONIMBOTDELETE"):
            dialog_id = (
                payload.get("data[PARAMS][DIALOG_ID]")
                or payload.get("data[DIALOG_ID]")
                or payload.get("DIALOG_ID")
                or payload.get("data[PARAMS][CHAT_ID]")
            )
            text = (
                payload.get("data[PARAMS][MESSAGE]")
                or payload.get("data[MESSAGE]")
                or payload.get("MESSAGE")
                or ""
            )

            # Se quiser usar sua lógica de IA:
            resposta = text.strip()
            if not resposta:
                resposta = "❗Mensagem vazia ou sem arquivo. Por favor, envie um texto ou anexo válido."
            resposta = _limpar_marcadores_de_citacao(resposta)

            
            # Verifica se o evento é direcionado a este BOT_ID (quando disponível no payload)
            # Bitrix envia, em muitos casos, data[PARAMS][BOT_ID] com o id do bot alvo
            bot_id_event = (
                payload.get("data[PARAMS][BOT_ID]")
                or payload.get("data[BOT_ID]")
                or payload.get("BOT_ID")
            )
            TARGET_BOT_ID = os.getenv("BOT_ID")  # defina no Render: BOT_ID=134
            if TARGET_BOT_ID and bot_id_event and str(bot_id_event) != str(TARGET_BOT_ID):
                app.logger.info(f"Ignorando evento de outro bot (evento BOT_ID={bot_id_event}, alvo={TARGET_BOT_ID})")
                return jsonify({"status": "ignored_different_bot"}), 200

            # Envia resposta AO NOVO BOT (força o remetente pelo BOT_ID)
            try:
                if not BITRIX_WEBHOOK:
                    app.logger.error("BITRIX_WEBHOOK não definido; não será possível responder no chat.")
                else:
                    BOT_ID_ENV = os.getenv("BOT_ID")
                    if not BOT_ID_ENV:
                        app.logger.error("BOT_ID (env) não definido; configure BOT_ID=134 no Render.")
                    url_bot = f"{BITRIX_WEBHOOK}/imbot.message.add"
                    data = {"BOT_ID": BOT_ID_ENV, "DIALOG_ID": dialog_id, "MESSAGE": resposta}
                    r = requests.post(url_bot, data=data, timeout=20)
                    app.logger.info(f"imbot.message.add status={r.status_code} resp={r.text}")
            except Exception as e:
                app.logger.error(f"Falha ao enviar resposta ao Bitrix: {e}")

            return jsonify({"status": "ok"}), 200

        return jsonify({"status": "ignored", "event": event}), 200
    except Exception as e:
        app.logger.error(f"Erro no /handler: {e}")
        return jsonify({"status":"error", "message": str(e)}), 500
# ====== fim /handler ======

# ====== Bitrix /handler (robusto: JSON + x-www-form-urlencoded) ======
import logging, re
from utils_assistant import run_assistant_and_get_text, send_bitrix_message

logging.basicConfig(level=logging.INFO)
BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK", "https://laboratoriocac.bitrix24.com.br/rest/1/ycsu4kix9ahlcff0/")

def _flatten_form_all(form):
    """Preserva todos os campos como chegam (inclusive chaves tipo data[PARAMS][...])."""
    out = {}
    try:
        items = form.items(multi=True)  # Werkzeug MultiDict
        for k, v in items:
            if k in out:
                # transforme em lista
                if isinstance(out[k], list):
                    out[k].append(v)
                else:
                    out[k] = [out[k], v]
            else:
                out[k] = v
    except Exception:
        # fallback simples
        for k in form.keys():
            out[k] = form.getlist(k) if hasattr(form, "getlist") else form.get(k)
    return out

def _pick(keys, d):
    for k in keys:
        if k in d and d[k]:
            return d[k]
    return None

@app.route("/handler", methods=["POST"])
def bitrix_handler():
    # Aceita JSON e form-urlencoded
    payload = request.get_json(silent=True)
    content_type = request.headers.get("Content-Type","")
    if not payload:
        payload = _flatten_form_all(request.form)

    app.logger.info(f"[HANDLER] ct={content_type}")
    app.logger.info(f"[HANDLER] payload={payload}")

    # Evento
    evt = (payload.get("event") or payload.get("EVENT") or "").upper()
    if evt in ("ONIMBOTMESSAGEADD", "ONIMBOTJOINCHAT", "ONIMBOTDELETE"):
        # Extração abrangente de IDs e mensagem
        dialog_id = _pick([
            "data[PARAMS][DIALOG_ID]","data[DIALOG_ID]","DIALOG_ID",
            "data[PARAMS][CHAT_ID]","CHAT_ID"], payload)
        text = _pick(["data[PARAMS][MESSAGE]","data[MESSAGE]","MESSAGE"], payload) or ""

        # Se nada veio, tenta pegar mensagem crua
        if not text and isinstance(payload, dict):
            for k,v in payload.items():
                if "MESSAGE" in k and isinstance(v, str):
                    text = v; break

        # 1) Roda o assistant e obtém resposta
        resposta = run_assistant_and_get_text(text, timeout_s=18)

        # 2) Envia ao Bitrix (sem precisar forçar BOT_ID se não quiser)
        try:
            r = send_bitrix_message(dialog_id, resposta)
            app.logger.info(f"[send_bitrix_message] {r}")
        except Exception as e:
            app.logger.error(f"Falha ao enviar ao Bitrix: {e}")

        # 3) Retorna 200 rápido
        return jsonify({"status":"ok"}), 200

    # Outros eventos: retorna 200 para não gerar retry
    return jsonify({"status":"ignored","event":evt}), 200
# ====== fim /handler ======

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render define a porta via variável de ambiente
    app.run(host="0.0.0.0", port=port)
