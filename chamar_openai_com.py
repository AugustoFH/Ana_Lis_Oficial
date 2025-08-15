# chamar_openai_com.py
import os, time, requests, logging

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID   = os.getenv("ASSISTANT_ID")  # ex.: asst_...

log = logging.getLogger(__name__)

def chamar_openai_com(user_text: str, timeout_s: int = 25) -> str:
    if not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY ausente.")
        return "⚠️ Configuração da IA ausente (OPENAI_API_KEY)."
    if not ASSISTANT_ID:
        log.error("ASSISTANT_ID ausente.")
        return "⚠️ Configuração da IA ausente (ASSISTANT_ID)."

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    try:
        # 1) Thread
        r = requests.post("https://api.openai.com/v1/threads", headers=headers, json={}, timeout=15)
        r.raise_for_status()
        thread_id = r.json()["id"]

        # 2) Mensagem do usuário
        r = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=headers, json={"role": "user", "content": user_text}, timeout=15
        )
        r.raise_for_status()

        # 3) Run
        r = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/runs",
            headers=headers, json={"assistant_id": ASSISTANT_ID}, timeout=15
        )
        r.raise_for_status()
        run_id = r.json()["id"]

        # 4) Poll até completar
        t0 = time.time()
        while True:
            rr = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                headers=headers, timeout=15
            )
            rr.raise_for_status()
            st = rr.json()["status"]
            if st in ("completed", "failed", "cancelled", "expired"):
                break
            if time.time() - t0 > timeout_s:
                log.warning(f"Timeout aguardando run {run_id} (status atual: {st})")
                return "⏳ Ainda processando sua solicitação. Tente novamente em alguns segundos."
            time.sleep(0.75)

        if st != "completed":
            log.error(f"Run não completou: status={st} run={run_id}")
            return f"❗Falha no processamento (status: {st})."

        # 5) Buscar a resposta do assistant
        mm = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=headers, params={"limit": 10}, timeout=15
        )
        mm.raise_for_status()
        for m in mm.json().get("data", []):
            if m.get("role") == "assistant":
                parts = []
                for c in m.get("content", []):
                    if c.get("type") == "text":
                        parts.append(c["text"]["value"])
                if parts:
                    text = "\n".join(parts).strip()
                    return text

        log.error("Não encontrei conteúdo de resposta do assistant.")
        return "❗Não encontrei conteúdo de resposta do assistant."

    except requests.exceptions.RequestException as e:
        # Log detalhado do erro HTTP
        detail = ""
        if getattr(e, "response", None) is not None:
            try:
                detail = f" | OpenAI {e.response.status_code}: {e.response.text[:400]}"
            except Exception:
                detail = f" | OpenAI {e.response.status_code}"
        log.error(f"Erro ao chamar OpenAI: {e}{detail}")
        return "❗Erro ao processar com a IA. Tente novamente."
