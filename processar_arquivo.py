import requests
from io import BytesIO
from PIL import Image
import mimetypes
from openai import OpenAI
import os
import time

openai_client = OpenAI(api_key=os.getenv("API_KEY"))
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

def is_image(file_bytes, content_type):
    if "image" not in content_type:
        print("❌ Conteúdo não é uma imagem (content-type).")
        return False
    try:
        img = Image.open(BytesIO(file_bytes))
        img.verify()
        return True
    except Exception as e:
        print("🛑 Erro ao verificar imagem:", e)
        return False

def processar_arquivo_do_bitrix(arquivo_url: str, arquivo_nome: str) -> str:
    try:
        print(f"🔗 URL: {arquivo_url}")
        print(f"🔽 Baixando arquivo: {arquivo_nome}")

        response = requests.get(arquivo_url, allow_redirects=True)

        if response.status_code != 200:
            return f"❌ Não foi possível acessar o link do arquivo. Código HTTP: {response.status_code}"

        content_type = response.headers.get("Content-Type", "")
        print(f"📦 Tipo de conteúdo recebido: {content_type}")

        file_bytes = response.content

        if not is_image(file_bytes, content_type):
            return "❌ O tipo de arquivo não é reconhecido como imagem compatível para análise."

        # Upload do arquivo para OpenAI
        upload_response = openai_client.files.create(
            file=BytesIO(file_bytes),
            purpose="assistants"
        )

        file_id = upload_response.id
        print(f"📎 Arquivo enviado à OpenAI. ID: {file_id}")

        # Criar thread
        thread = openai_client.beta.threads.create()
        run = openai_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
            instructions="Analise a imagem enviada e forneça uma resposta útil à equipe do laboratório."
        )

        # Adiciona a imagem como mensagem
        openai_client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=[
                {"type": "text", "text": "Por favor, analise esta imagem."},
                {"type": "image_file", "image_file": {"file_id": file_id}}
            ]
        )

        while True:
            status = openai_client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if status.status == "completed":
                break
            elif status.status == "failed":
                return "❗Erro ao processar imagem com a IA."
            time.sleep(1)

        resposta = openai_client.beta.threads.messages.list(thread_id=thread.id)
        return resposta.data[0].content[0].text.value.strip()

    except Exception as e:
        print("❌ Erro em processar_arquivo_do_bitrix:", e)
        return "❗Ocorreu um erro ao processar o arquivo."
