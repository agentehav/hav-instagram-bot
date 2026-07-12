# Instagram HAV — automação de postagem diária

Robô que posta 1 imagem por dia no Instagram do Hospital Amigo Veterinário,
sozinho, sem precisar de PC ligado. Roda na nuvem (GitHub Actions).

## Como funciona

1. Todo dia às **18h (horário de Brasília)**, o GitHub dispara o workflow
   automaticamente.
2. O script `postar_instagram.py` olha o arquivo `fila-postagem.txt`, pega o
   **primeiro item que ainda não tem `[POSTADO]`**.
3. Procura a imagem e a legenda correspondentes na pasta `posts/`.
4. Publica no Instagram via API do Facebook/Meta (Graph API).
5. Marca o item como `[POSTADO]` na fila e salva isso de volta no repositório
   (commit automático).

Repositório: https://github.com/agentehav/hav-instagram-bot (público — não
tem nenhuma senha ou token dentro dele, só imagens/legendas que iam pro
Instagram público mesmo).

## Onde ficam as credenciais

Não estão em nenhum arquivo do repositório. Ficam guardadas de forma
criptografada em **Settings → Secrets and variables → Actions** do repo:

- `IG_ACCESS_TOKEN` — token de acesso da página do Facebook/Instagram
- `IG_BUSINESS_ID` — ID da conta Instagram Business (`17841459649764912`)

Se o token expirar ou for revogado (tokens de página do Facebook podem
expirar), é preciso gerar um novo no
[Meta for Developers](https://developers.facebook.com/) e atualizar o
secret com:

```
gh secret set IG_ACCESS_TOKEN --body "NOVO_TOKEN_AQUI" --repo agentehav/hav-instagram-bot
```

## Como adicionar novos posts na fila

### Imagem única

1. Gerar a imagem (ver `Scripts/gerar_imagem.py` no projeto principal
   "Agente HAV", pasta fora deste repo) ou criar manualmente.
2. Colocar a imagem `.png` e a legenda `.txt` dentro da pasta `posts/` deste
   repositório. **O nome do arquivo tem que seguir o padrão**
   `post-NOME-DO-POST.png` e `post-NOME-DO-POST.txt` (mesmo `NOME-DO-POST`
   nos dois).
3. Adicionar uma linha nova em `fila-postagem.txt`, no formato:
   ```
   13. nome-do-post
   ```
4. Commitar e dar push:
   ```
   git add posts/ fila-postagem.txt
   git commit -m "add: novo post nome-do-post"
   git push
   ```

### Carrossel (várias imagens no mesmo post)

1. Criar uma pasta dentro de `posts/` com o nome do post:
   `posts/nome-do-post/`
2. Colocar as imagens numeradas dentro, na ordem que devem aparecer:
   `1.png`, `2.png`, `3.png`, ... (entre 2 e 10 imagens — limite do
   Instagram).
3. Colocar a legenda em `posts/nome-do-post/legenda.txt` (um arquivo só,
   vale pro carrossel inteiro).
4. Adicionar a mesma linha de sempre em `fila-postagem.txt`:
   ```
   13. nome-do-post
   ```
   O robô detecta sozinho que é carrossel (é uma pasta, não um arquivo
   `post-nome-do-post.png`) e publica todas as imagens juntas.
5. Commitar e dar push normalmente.

## Como rodar manualmente (sem esperar o horário)

Precisa ter o [GitHub CLI](https://cli.github.com/) instalado e logado
(`gh auth login`):

```
gh workflow run postar-diario.yml --repo agentehav/hav-instagram-bot
```

Acompanhar o resultado:

```
gh run list --workflow=postar-diario.yml --repo agentehav/hav-instagram-bot --limit 1
gh run view --repo agentehav/hav-instagram-bot --log
```

Ou direto no navegador:
https://github.com/agentehav/hav-instagram-bot/actions

## Como pausar ou desligar o robô

Editar `.github/workflows/postar-diario.yml` e comentar a parte do
`schedule`:

```yaml
on:
  workflow_dispatch: {}
  # schedule:
  #   - cron: "0 21 * * *"
```

Commitar e dar push. Sem o `schedule` ativo, ele só posta quando você
disparar manualmente (`gh workflow run`).

## O que fazer quando a fila acabar

Quando todos os itens de `fila-postagem.txt` estiverem `[POSTADO]`, o robô
avisa "Fila vazia, nada pra postar" e não faz nada (não dá erro). É preciso
gerar posts novos e repetir o passo "Como adicionar novos posts na fila"
acima.

**Atenção:** em 2026-07-12, 3 posts da fila do projeto original ainda não
tinham imagem gerada (`primeiros-socorros`, `castracao-mitos`,
`ansiedade-separacao`). Quando a fila chegar neles sem imagem em `posts/`,
o robô **falha aquele dia** (não posta nada errado, só para e avisa no log
do GitHub Actions) — não vai travar os dias seguintes.

## Problemas conhecidos

- **catbox.moe bloqueia GitHub Actions** (erro 412) — por isso as imagens
  são servidas direto do próprio repositório via
  `raw.githubusercontent.com`, sem depender de host de imagem terceiro.
  Se um dia trocar de estratégia de hospedagem, lembrar desse bloqueio.
- Se o post falhar por token expirado, o erro aparece no log do Actions
  como `401` ou `OAuthException` — sinal pra gerar token novo (ver seção
  de credenciais acima).
