# chamar_openai_com.py
import os, time, requests, logging

log = logging.getLogger("chamar_openai_com")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID   = os.getenv("ASSISTANT_ID")          # ex.: asst_...
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gpt-4o-mini")

def _headers():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY ausente.")
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v2",  # OBRIGATÓRIO p/ Threads/Runs
    }

def _headers_no_beta():
    # para Chat Completions (não usa o Beta header)
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY ausente.")
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

def _fallback_completion(user_text: str) -> str:
    """Se a Assistants API falhar, usa Chat Completions para responder."""
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_headers_no_beta(),
            json={
                "model": FALLBACK_MODEL,
                "messages": [
                    {"role": "system", "content": "Você é a Ana Lis - Agente IA, assistente objetiva e cordial."},
                    {"role": "user", "content": user_text}
                ],
                "temperature": 0.4,
                "max_tokens": 500
            },
            timeout=20
        )
        r.raise_for_status()
        data = r.json()
        txt = data["choices"][0]["message"]["content"].strip()
        return txt
    except requests.exceptions.RequestException as e:
        detail = ""
        if getattr(e, "response", None) is not None:
            try:
                detail = f" | OpenAI {e.response.status_code}: {e.response.text[:400]}"
            except Exception:
                detail = f" | OpenAI {e.response.status_code}"
        log.error(f"Fallback (chat completions) falhou: {e}{detail}")
        return "❗Erro ao processar com a IA. Tente novamente."

def chamar_openai_com(user_text: str, timeout_s: int = 25) -> str:
    if not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY ausente.")
        return "⚠️ Configuração da IA ausente (OPENAI_API_KEY)."
    if not ASSISTANT_ID:
        log.error("ASSISTANT_ID ausente.")
        return "⚠️ Configuração da IA ausente (ASSISTANT_ID)."

    try:
        # 1) Cria thread
        r = requests.post("https://api.openai.com/v1/threads", headers=_headers(), json={}, timeout=15)
        r.raise_for_status()
        thread_id = r.json()["id"]

        # 2) Mensagem do usuário
        r = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=_headers(),
            json={"role": "user", "content": user_text},
            timeout=15
        )
        r.raise_for_status()

        # 3) Run
        r = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/runs",
            headers=_headers(),
            json={"assistant_id": ASSISTANT_ID},
            timeout=15
        )
        r.raise_for_status()
        run_id = r.json()["id"]

        # 4) Poll
        t0 = time.time()
        status = None
        while True:
            rr = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                headers=_headers(),
                timeout=15
            )
            rr.raise_for_status()
            run_obj = rr.json()
            status = run_obj.get("status")
            if status in ("completed", "failed", "cancelled", "expired", "requires_action"):
                break
            if time.time() - t0 > timeout_s:
                log.warning(f"Timeout aguardando run {run_id} (status atual: {status})")
                # Usa fallback para ainda responder o usuário
                return _fallback_completion(user_text)
            time.sleep(0.7)

        # 5) Trata terminais
        if status == "completed":
            # Busca mensagens
            mm = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/messages",
                headers=_headers(),
                params={"limit": 10},
                timeout=15
            )
            mm.raise_for_status()
            for m in mm.json().get("data", []):
                if m.get("role") == "assistant":
                    parts = []
                    for c in m.get("content", []):
                        if c.get("type") == "text":
                            parts.append(c["text"]["value"])
                    if parts:
                        return "\n".join(parts).strip()
            log.error("Não encontrei conteúdo de resposta do assistant.")
            return _fallback_completion(user_text)

        elif status == "requires_action":
            # Seu assistant tem ferramentas externas definidas (function calling)
            # e está aguardando "tool outputs". Como não tratamos aqui,
            # registra e cai no fallback para não travar.
            log.error(f"Run requer ação externa (tool outputs). run={run_id} obj={run_obj}")
            return _fallback_completion(user_text)

        else:
            # failed / cancelled / expired → logar motivo e fallback
            last_err = None
            try:
                last_err = run_obj.get("last_error")  # {'code': '...', 'message': '...'}
            except Exception:
                pass
            log.error(f"Run não completou: status={status} run={run_id} last_error={last_err}")
            return _fallback_completion(user_text)

    except requests.exceptions.RequestException as e:
        detail = ""
        if getattr(e, "response", None) is not None:
            try:
                detail = f" | OpenAI {e.response.status_code}: {e.response.text[:400]}"
            except Exception:
                detail = f" | OpenAI {e.response.status_code}"
        log.error(f"Erro ao chamar OpenAI: {e}{detail}")
        return _fallback_completion(user_text)
