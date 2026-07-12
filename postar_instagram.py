"""
Publica o proximo post pendente da fila no Instagram HAV: cria o media
container na Graph API (imagem unica ou carrossel) e publica. Marca o
item como [POSTADO] na fila.

Post de imagem unica: posts/post-{nome}.png + posts/post-{nome}.txt
Post de carrossel: pasta posts/{nome}/ com imagens numeradas (1.png,
2.png, ...) e posts/{nome}/legenda.txt

Roda no GitHub Actions. Credenciais vem de variaveis de ambiente:
    IG_ACCESS_TOKEN, IG_BUSINESS_ID
"""

import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
FILA_PATH = ROOT / "fila-postagem.txt"
ULTIMO_POST_PATH = ROOT / "ultimo_post.txt"

GRAPH_VERSION = "v21.0"
REPO = "agentehav/hav-instagram-bot"
BRANCH = "main"
BRASILIA = timezone(timedelta(hours=-3))


def hoje_brasilia() -> str:
    return datetime.now(BRASILIA).date().isoformat()


def ja_postou_hoje() -> bool:
    if not ULTIMO_POST_PATH.exists():
        return False
    return ULTIMO_POST_PATH.read_text(encoding="utf-8").strip() == hoje_brasilia()


def marcar_data_post() -> None:
    ULTIMO_POST_PATH.write_text(hoje_brasilia() + "\n", encoding="utf-8")


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


def eh_carrossel(nome_post: str) -> bool:
    return (POSTS_DIR / nome_post).is_dir()


def encontrar_arquivos(nome_post: str) -> tuple[Path, Path] | None:
    imagens = sorted(POSTS_DIR.glob(f"*post-{nome_post}.png"))
    legendas = sorted(POSTS_DIR.glob(f"*post-{nome_post}.txt"))
    if not imagens or not legendas:
        return None
    return imagens[-1], legendas[-1]


def encontrar_carrossel(nome_post: str) -> tuple[list[Path], Path] | None:
    pasta = POSTS_DIR / nome_post
    imagens = sorted(pasta.glob("*.png"), key=lambda p: p.name)
    legenda = pasta / "legenda.txt"
    if not imagens or not legenda.exists():
        return None
    if not (2 <= len(imagens) <= 10):
        raise SystemExit(
            f"Carrossel '{nome_post}' tem {len(imagens)} imagens; "
            "Instagram exige entre 2 e 10."
        )
    return imagens, legenda


def url_imagem_publica(caminho_imagem: Path) -> str:
    rel = caminho_imagem.relative_to(POSTS_DIR).as_posix()
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/posts/{rel}"


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


def criar_item_carrossel(image_url: str, token: str, business_id: str) -> str:
    resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{business_id}/media",
        data={"image_url": image_url, "is_carousel_item": "true", "access_token": token},
    )
    resp.raise_for_status()
    dados = resp.json()
    if "id" not in dados:
        raise SystemExit(f"Falha ao criar item do carrossel: {dados}")
    return dados["id"]


def criar_container_carrossel(children_ids: list[str], legenda: str, token: str, business_id: str) -> str:
    resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{business_id}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": legenda,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    dados = resp.json()
    if "id" not in dados:
        raise SystemExit(f"Falha ao criar container do carrossel: {dados}")
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
    if ja_postou_hoje():
        print(f"Ja postou hoje ({hoje_brasilia()}). Pulando pra evitar post duplicado no dia.")
        return

    token, business_id = carregar_credenciais()

    nome_post = proximo_da_fila()
    if nome_post is None:
        print("Fila vazia, nada pra postar.")
        return

    if eh_carrossel(nome_post):
        carrossel = encontrar_carrossel(nome_post)
        if carrossel is None:
            print(f"AVISO: pasta '{nome_post}' existe mas sem imagens/legenda.txt validos. Pulando.")
            sys.exit(1)
        imagens, caminho_legenda = carrossel
        legenda = caminho_legenda.read_text(encoding="utf-8").strip()

        children_ids = []
        for caminho_imagem in imagens:
            image_url = url_imagem_publica(caminho_imagem)
            print(f"Item do carrossel: {image_url}")
            item_id = criar_item_carrossel(image_url, token, business_id)
            aguardar_pronto(item_id, token)
            children_ids.append(item_id)
        print(f"OK: {len(children_ids)} itens prontos")

        print("Criando container do carrossel...")
        container_id = criar_container_carrossel(children_ids, legenda, token, business_id)
        print(f"OK: container {container_id}")

        print("Aguardando processamento...")
        aguardar_pronto(container_id, token)
    else:
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
    marcar_data_post()
    print(f"Fila atualizada: {nome_post} [POSTADO]")


if __name__ == "__main__":
    main()
