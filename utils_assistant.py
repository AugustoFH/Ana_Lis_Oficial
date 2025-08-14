import os, time, requests, re

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID   = os.getenv("ASSISTANT_ID")
BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")  # ex.: https://.../rest/1/<token>/
BOT_ID         = os.getenv("BOT_ID")          # opcional; se vazio, envia sem BOT_ID

def strip_citations(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"[].*?[]", "", text)
    return text.replace("","").replace("","").replace("","")

def run_assistant_and_get_text(user_text: str, timeout_s: int = 18) -> str:
    """Executa Assistants API e retorna a última resposta textual do assistant."""
    if not (OPENAI_API_KEY and ASSISTANT_ID):
        return "❗Configuração ausente: OPENAI_API_KEY ou ASSISTANT_ID."
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    r = requests.post("https://api.openai.com/v1/threads", headers=headers, json={})
    r.raise_for_status()
    thread_id = r.json()["id"]

    r = requests.post(f"https://api.openai.com/v1/threads/{thread_id}/messages",
                      headers=headers, json={"role":"user","content":user_text})
    r.raise_for_status()

    r = requests.post(f"https://api.openai.com/v1/threads/{thread_id}/runs",
                      headers=headers, json={"assistant_id": ASSISTANT_ID})
    r.raise_for_status()
    run_id = r.json()["id"]

    import time as _t
    t0 = _t.time()
    while True:
        r = requests.get(f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}", headers=headers)
        r.raise_for_status()
        st = r.json()["status"]
        if st in ("completed","failed","cancelled","expired"):
            break
        if _t.time() - t0 > timeout_s:
            return "⚠️ Processando sua solicitação; tente novamente em instantes."
        _t.sleep(0.7)

    if st != "completed":
        return f"❗Não consegui completar a resposta (status: {st})."

    r = requests.get(f"https://api.openai.com/v1/threads/{thread_id}/messages",
                     headers=headers, params={"limit": 10})
    r.raise_for_status()
    data = r.json().get("data", [])
    for m in data:
        if m.get("role") == "assistant":
            parts = []
            for c in m.get("content", []):
                if c.get("type") == "text":
                    parts.append(c["text"]["value"])
            if parts:
                return strip_citations("\n".join(parts).strip())
    return "❗Sem conteúdo de resposta do assistant."
    
def send_bitrix_message(dialog_id: str, text: str) -> dict:
    """Envia mensagem via Bitrix. Se BOT_ID presente, usa imbot.message.add; senão tenta im.message.add."""
    if not BITRIX_WEBHOOK:
        raise RuntimeError("BITRIX_WEBHOOK não configurado.")
    text = strip_citations(text or "")
    if BOT_ID:
        url = f"{BITRIX_WEBHOOK}/imbot.message.add"
        resp = requests.post(url, data={"BOT_ID": BOT_ID, "DIALOG_ID": dialog_id, "MESSAGE": text}, timeout=15)
    else:
        # fallback quando não queremos forçar o bot_id
        url = f"{BITRIX_WEBHOOK}/im.message.add"
        resp = requests.post(url, data={"DIALOG_ID": dialog_id, "MESSAGE": text}, timeout=15)
    try:
        j = resp.json()
    except Exception:
        j = {"raw": resp.text}
    return {"status_code": resp.status_code, "body": j}
