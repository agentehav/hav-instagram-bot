"""
Publica o proximo post pendente da fila no Instagram HAV: sobe a imagem
no catbox.moe (upload anonimo), cria o media container na Graph API e
publica. Marca o item como [POSTADO] na fila.

Roda no GitHub Actions. Credenciais vem de variaveis de ambiente:
    IG_ACCESS_TOKEN, IG_BUSINESS_ID
"""

import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
FILA_PATH = ROOT / "fila-postagem.txt"

GRAPH_VERSION = "v21.0"
REPO = "agentehav/hav-instagram-bot"
BRANCH = "main"


def carregar_credenciais() -> tuple[str, str]:
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    business_id = os.environ.get("IG_BUSINESS_ID", "")
    if not token or not business_id:
        raise SystemExit("IG_ACCESS_TOKEN ou IG_BUSINESS_ID nao definidos no ambiente")
    return token, business_id


def proximo_da_fila() -> str | None:
    linhas = FILA_PATH.read_text(encoding="utf-8").splitlines()
    for linha in linhas:
        m = re.match(r"^\d+\.\s+([\w-]+)", linha.strip())
        if m and "[POSTADO]" not in linha:
            return m.group(1)
    return None


def encontrar_arquivos(nome_post: str) -> tuple[Path, Path] | None:
    imagens = sorted(POSTS_DIR.glob(f"*post-{nome_post}.png"))
    legendas = sorted(POSTS_DIR.glob(f"*post-{nome_post}.txt"))
    if not imagens or not legendas:
        return None
    return imagens[-1], legendas[-1]


def url_imagem_publica(caminho_imagem: Path) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/posts/{caminho_imagem.name}"


def criar_media_container(image_url: str, legenda: str, token: str, business_id: str) -> str:
    resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{business_id}/media",
        data={"image_url": image_url, "caption": legenda, "access_token": token},
    )
    resp.raise_for_status()
    dados = resp.json()
    if "id" not in dados:
        raise SystemExit(f"Falha ao criar container: {dados}")
    return dados["id"]


def aguardar_pronto(container_id: str, token: str, tentativas: int = 10, espera_s: int = 3) -> None:
    for _ in range(tentativas):
        resp = requests.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{container_id}",
            params={"fields": "status_code", "access_token": token},
        )
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise SystemExit(f"Container falhou ao processar: {resp.json()}")
        time.sleep(espera_s)
    raise SystemExit("Timeout esperando container ficar pronto (status FINISHED)")


def publicar(container_id: str, token: str, business_id: str) -> str:
    resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{business_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
    )
    resp.raise_for_status()
    dados = resp.json()
    if "id" not in dados:
        raise SystemExit(f"Falha ao publicar: {dados}")
    return dados["id"]


def marcar_postado(nome_post: str) -> None:
    linhas = FILA_PATH.read_text(encoding="utf-8").splitlines()
    novas = []
    for linha in linhas:
        if nome_post in linha and "[POSTADO]" not in linha:
            linha = linha.rstrip() + " [POSTADO]"
        novas.append(linha)
    FILA_PATH.write_text("\n".join(novas) + "\n", encoding="utf-8")


def main() -> None:
    token, business_id = carregar_credenciais()

    nome_post = proximo_da_fila()
    if nome_post is None:
        print("Fila vazia, nada pra postar.")
        return

    arquivos = encontrar_arquivos(nome_post)
    if arquivos is None:
        print(f"AVISO: '{nome_post}' esta na fila mas sem imagem/legenda em posts/. Pulando.")
        sys.exit(1)

    caminho_imagem, caminho_legenda = arquivos
    legenda = caminho_legenda.read_text(encoding="utf-8").strip()

    image_url = url_imagem_publica(caminho_imagem)
    print(f"Imagem: {image_url}")

    print("Criando media container na Graph API...")
    container_id = criar_media_container(image_url, legenda, token, business_id)
    print(f"OK: container {container_id}")

    print("Aguardando processamento...")
    aguardar_pronto(container_id, token)

    print("Publicando...")
    post_id = publicar(container_id, token, business_id)
    print(f"OK: publicado, id {post_id}")

    marcar_postado(nome_post)
    print(f"Fila atualizada: {nome_post} [POSTADO]")


if __name__ == "__main__":
    main()
