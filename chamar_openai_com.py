
from openai import OpenAI
import os
import time

openai_client = OpenAI(api_key=os.getenv("API_KEY"))
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

def chamar_openai_com(mensagem_usuario: str) -> str:
    try:
        thread = openai_client.beta.threads.create()

        openai_client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=mensagem_usuario
        )

        run = openai_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
            instructions="Responda com base nas orientações internas do laboratório."
        )

        while True:
            status = openai_client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if status.status == "completed":
                break
            elif status.status == "failed":
                return "❗Erro ao processar com a IA. Tente novamente."
            time.sleep(1)

        resposta = openai_client.beta.threads.messages.list(thread_id=thread.id)
        return resposta.data[0].content[0].text.value.strip()

    except Exception as e:
        print("❌ Erro em chamar_openai_com:", e)
        return "❗Ocorreu um erro interno ao conversar com a IA."
