# Executar as imagens publicadas no GHCR

Este guia inicia API, Web e Analytics usando as imagens publicadas no GitHub Container Registry, sem reconstruir os Dockerfiles localmente.

## Requisitos

- Docker Engine e Docker Compose v2.
- Acesso ao GitHub Container Registry.
- Catálogo local do TSE gerado antes da inicialização.

## 1. Obter o catálogo

Na raiz do repositório clonado:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/discover_tse_catalog.py
```

A descoberta consulta o CKAN do TSE e grava os metadados em `catalog/tse/datasets/`. O processo precisa de acesso à internet. Não use um manifesto vazio como se fosse uma coleta concluída.

## 2. Autenticar no GHCR, se necessário

Se os pacotes estiverem públicos, o login não é necessário. Se estiverem privados:

```powershell
$env:GHCR_TOKEN | docker login ghcr.io -u SEU_USUARIO_GITHUB --password-stdin
```

O token precisa ter permissão `read:packages`. Para distribuição sem autenticação, configure a visibilidade dos três pacotes como Public nas configurações de Packages do GitHub.

## 3. Iniciar os serviços

A versão padrão é `v0.1.0-alpha.2`. Para selecionar outra tag:

```powershell
$env:IMAGE_TAG = "v0.1.0-alpha.2"
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

A interface Web consulta a API pelo endereço local `http://localhost:3001`, e os três serviços ficam disponíveis em:

| Serviço | Endereço |
|---|---|
| Web | http://localhost:3000 |
| API health | http://localhost:3001/health |
| API catálogo | http://localhost:3001/api/v1/catalog |
| Relatório HTML | http://localhost:8501/catalog/index.html |

## 4. Verificar e encerrar

```powershell
docker compose -f docker-compose.ghcr.yml ps
docker compose -f docker-compose.ghcr.yml logs -f
docker compose -f docker-compose.ghcr.yml down
```

## Observações

- O Compose usa imagens preexistentes; não executa build local.
- O diretório `catalog` é montado como somente leitura nos serviços que consomem metadados.
- O serviço Analytics serve um relatório HTML estático de metadados do catálogo CKAN em `http://localhost:8501/catalog/index.html`. Ele não deve ser interpretado como painel de votos ou resultados eleitorais. A imagem GHCR `v0.1.0-alpha.2` antecede esta migração; publique uma nova release para distribuir a versão HTML.
- Esta composição é destinada a desenvolvimento e avaliação. Não configura TLS, autenticação da aplicação, proxy reverso, backups ou hardening de produção.
- A tag alpha é uma versão de pré-lançamento e pode sofrer alterações incompatíveis.
