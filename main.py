import os
import re
import time
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify

# Suas funções existentes
from processar_arquivo import processar_arquivo_do_bitrix
from chamar_openai_com import chamar_openai_com  # Função separada

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# =========================
# Configurações
# =========================
# Controle de horário (desabilitado por padrão)
HABILITAR_RESTRICAO_HORARIO = False

# Identidade (cosmético)
BOT_NAME = "Ana Lis - Agente IA"
BOT_COLOR = "ORANGE"
WELCOME_MESSAGE = "Olá! Sou a Ana Lis - Agente IA, sua assistente virtual. Como posso te ajudar?"

# URLs e Webhook
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://lis-v2-bot.onrender.com")
# NOVO webhook informado por você:
WEBHOOK_KEY_DEFAULT = "ycsu4kix9ahlcff0"
BITRIX_WEBHOOK = os.getenv(
    "BITRIX_WEBHOOK",
    f"https://laboratoriocac.bitrix24.com.br/rest/1/{WEBHOOK_KEY_DEFAULT}"
)

# =========================
# Utilitários
# =========================
def limpar_marcadores_de_citacao(resposta: str) -> str:
    """Remove marcadores especiais que podem aparecer em algumas respostas."""
    if not isinstance(resposta, str):
        return resposta
    resposta = re.sub(r"[].*?[]", "", resposta or "")
    return resposta.replace("", "")

def _flatten_form_all(form):
    """Preserva todos os campos do form (MultiDict) como chegam (inclusive data[PARAMS][...])."""
    out = {}
    try:
        for k, v in form.items(multi=True):
            if k in out:
                if isinstance(out[k], list):
                    out[k].append(v)
                else:
                    out[k] = [out[k], v]
            else:
                out[k] = v
    except Exception:
        # fallback simples
        for k in form.keys():
            if hasattr(form, "getlist"):
                vals = form.getlist(k)
                out[k] = vals if len(vals) > 1 else (vals[0] if vals else None)
            else:
                out[k] = form.get(k)
    return out

def _pick(keys, d):
    """Retorna o primeiro valor não-vazio encontrado em d para as chaves da lista keys."""
    for k in keys:
        if k in d and d[k]:
            return d[k]
    return None

def _send_im_message(dialog_id: str, text: str):
    """Envia mensagem como o usuário do webhook (im.message.add)."""
    url = f"{BITRIX_WEBHOOK}/im.message.add.json"
    body = {"DIALOG_ID": dialog_id, "MESSAGE": text}
    r = requests.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=15)
    app.logger.info(f"[im.message.add] status={r.status_code} resp={r.text[:400]}")
    return r

# =========================
# Rotas
# =========================
@app.route("/", methods=["GET"])
def home():
    return "Ana Lis - Agente IA está online!"

@app.route("/install", methods=["POST"])
def install():
    """
    Registra o bot no portal informando os endpoints de evento.
    Não usa CLIENT_ID (webhook inbound não precisa).
    """
    data = request.args.to_dict()
    app.logger.info(f"📦 Dados recebidos na instalação: {data}")

    domain = data.get("DOMAIN")
    protocol = "https" if data.get("PROTOCOL") == "1" else "http"

    if not domain:
        return jsonify({"erro": "Domain não especificado", "status": "Erro interno"}), 500

    # Usa o próprio portal + webhook para registrar
    # Ex.: https://<domain>/rest/1/<webhook_key>/imbot.register.json
    # Preferimos usar o WEBHOOK_KEY já ativo (do ambiente ou default)
    webhook_key = os.getenv("BITRIX_WEBHOOK", "").strip()
    if webhook_key and "/rest/" in webhook_key:
        # Se veio a URL completa em BITRIX_WEBHOOK, reaproveitamos o subpath após /rest/1/
        try:
            after_rest = webhook_key.split("/rest/1/")[1].strip("/")
        except Exception:
            after_rest = WEBHOOK_KEY_DEFAULT
        key_to_use = after_rest
    else:
        key_to_use = WEBHOOK_KEY_DEFAULT

    webhook_url = f"{protocol}://{domain}/rest/1/{key_to_use}/imbot.register.json"

    payload = {
        "CODE": "ana_lis_lab_cac_v2",
        "TYPE": "B",
        "EVENT_MESSAGE_ADD": f"{PUBLIC_URL}/handler",
        "EVENT_WELCOME_MESSAGE": f"{PUBLIC_URL}/handler",
        "EVENT_BOT_DELETE": f"{PUBLIC_URL}/handler",
        "OPENLINE": "N",
        "PROPERTIES": {
            "NAME": BOT_NAME,
            "COLOR": BOT_COLOR
        }
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=20)
        bitrix_result = {}
        try:
            bitrix_result = response.json()
        except Exception:
            bitrix_result = {"raw": response.text}
        app.logger.info(f"🛰️ Resposta do Bitrix: {bitrix_result}")
        return jsonify({"status": "Instalação recebida com sucesso", "bitrix_response": bitrix_result})
    except Exception as e:
        app.logger.error(f"Erro na instalação: {e}")
        return jsonify({"erro": str(e), "status": "Erro interno"}), 500

@app.route('/handler', methods=['POST'])
def bitrix_handler():
    """
    ÚNICO handler:
    - Aceita JSON e x-www-form-urlencoded
    - Extrai DIALOG_ID e MESSAGE de forma abrangente
    - Mantém sua lógica: texto -> chamar_openai_com; arquivo -> processar_arquivo_do_bitrix
    - Envia resposta para o Bitrix via im.message.add (sem forçar BOT_ID)
    - Retorna 200 rápido
    """
    try:
        # 1) Normaliza payload
        payload = request.get_json(silent=True)
        if not payload:
            payload = _flatten_form_all(request.form)

        app.logger.info(f"[HANDLER] ct={request.headers.get('Content-Type','')}")
        app.logger.info(f"[HANDLER] payload={payload}")

        # 2) Filtra eventos relevantes
        evt = (payload.get("event") or payload.get("EVENT") or "").upper()
        if evt not in ("ONIMBOTMESSAGEADD", "ONIMBOTJOINCHAT", "ONIMBOTDELETE"):
            return jsonify({"status": "ignored", "event": evt}), 200

        # 3) Extrai IDs e mensagem
        dialog_id = _pick([
            "data[PARAMS][DIALOG_ID]", "data[DIALOG_ID]", "DIALOG_ID",
            "data[PARAMS][CHAT_ID]", "CHAT_ID"
        ], payload)
        text = _pick(["data[PARAMS][MESSAGE]", "data[MESSAGE]", "MESSAGE"], payload) or ""

        if not dialog_id:
            return jsonify({"status": "no_dialog"}), 200

        # 4) Restrições de horário (opcional)
        if HABILITAR_RESTRICAO_HORARIO:
            hora = datetime.now().hour
            minuto = datetime.now().minute
            if hora < 6 or (hora == 6 and minuto < 30) or hora >= 23:
                mensagem_limite = "Ana Lis - Agente IA está disponível das 06:30 às 18:00. Por favor, retorne nesse horário 😊"
                try:
                    _send_im_message(dialog_id, mensagem_limite)
                except Exception as e:
                    app.logger.error(f"Falha ao enviar msg de limite: {e}")
                return jsonify({"status": "fora_do_horario"}), 200

        # 5) Detecta arquivo (mantém sua lógica)
        arquivo_url = None
        arquivo_nome = None
        if isinstance(payload, dict):
            for k, v in payload.items():
                if isinstance(k, str) and k.endswith("][urlDownload]") and "data[PARAMS][FILES][" in k:
                    arquivo_url = v
                    i = k.find("FILES[") + 6
                    j = k.find("]", i)
                    file_id = k[i:j]
                    arquivo_nome = payload.get(f"data[PARAMS][FILES][{file_id}][name]", "arquivo_desconhecido")
                    break

        # 6) Gera resposta com sua IA atual
        if arquivo_url and arquivo_nome:
            app.logger.info("📂 Arquivo detectado! Enviando ao processador de arquivo...")
            try:
                resposta_ia = processar_arquivo_do_bitrix(arquivo_url, arquivo_nome)
            except Exception as e:
                app.logger.error(f"processar_arquivo_do_bitrix erro: {e}")
                resposta_ia = "❌ O tipo de arquivo não é reconhecido como imagem compatível para análise."
        elif text:
            app.logger.info("💬 Mensagem de texto detectada! Enviando ao GPT...")
            try:
                resposta_ia = chamar_openai_com(text)
            except Exception as e:
                app.logger.error(f"chamar_openai_com erro: {e}")
                resposta_ia = "❗Ocorreu um erro ao processar sua mensagem."
            resposta_ia = limpar_marcadores_de_citacao(resposta_ia)
        else:
            resposta_ia = "❗Mensagem vazia ou sem arquivo. Por favor, envie um texto ou anexo válido."

        # 7) Envia ao Bitrix (como usuário do webhook, sem forçar BOT_ID)
        try:
            _send_im_message(dialog_id, resposta_ia)
        except Exception as e:
            app.logger.error(f"Falha ao enviar ao Bitrix: {e}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        app.logger.error(f"Erro no /handler: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# =========================
# Run
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render define a porta via variável de ambiente
    app.run(host="0.0.0.0", port=port)
