# Painel analítico Streamlit

O serviço Analytics utiliza Streamlit como interface analítica principal para explorar o catálogo CKAN do Tribunal Superior Eleitoral. O escopo desta primeira etapa é deliberadamente restrito aos metadados efetivamente descobertos.

## Execução local

Na raiz do repositório, com o ambiente virtual ativado:

```powershell
python -m pip install -r apps/analytics/requirements.txt
python scripts/discover_tse_catalog.py
streamlit run apps/analytics/app.py
```

A interface será disponibilizada em http://localhost:8501.

A descoberta grava o manifesto e os metadados individuais em `catalog/tse/datasets/`. O painel lê esse diretório; ele não baixa os arquivos eleitorais vinculados aos recursos.

## Execução com Docker Compose

```powershell
python scripts/discover_tse_catalog.py
docker compose up --build
```

O serviço Analytics fica disponível em http://localhost:8501. O diretório `catalog/` é montado no contêiner como somente leitura.

## Funcionalidades da primeira versão

- Visão geral com totais de conjuntos, recursos e órgãos.
- Gráficos Plotly para formatos, organizações e conjuntos com mais recursos.
- Filtros globais por órgão, formato e texto.
- Inventário pesquisável de conjuntos e respectivos metadados.
- Explorador de recursos com URL de origem, formato, tamanho e hash quando publicados.
- Exportação do recorte filtrado em CSV e Excel.

## Escopo e integridade analítica

Os indicadores representam metadados do catálogo CKAN. A contagem de recursos não equivale à quantidade de arquivos efetivamente baixados, processados ou validados.

O painel não apresenta resultados de votação, percentuais de comparecimento, abstenção, candidaturas processadas ou mapas eleitorais enquanto as respectivas bases não tiverem sido ingeridas, normalizadas e validadas.

O carregador aceita apenas arquivos JSON diretamente contidos no diretório do manifesto e ignora caminhos relativos que tentem escapar desse diretório.

## Organização técnica

- `app.py`: interface Streamlit, filtros, gráficos e exportações.
- `catalog_data.py`: leitura segura do manifesto e dos metadados CKAN.
- `test_catalog_data.py`: testes do carregador e da proteção contra path traversal.
- `requirements.txt`: dependências específicas da aplicação Analytics.
- `generate_report.py`: gerador HTML complementar, independente do painel Streamlit.
