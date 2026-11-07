# Relatórios HTML

O Brasil Eleitoral DataLab usa a aplicação Next.js em `apps/web` como interface principal. O componente Analytics gera relatórios HTML autônomos em Python, sem Streamlit e sem dependências Python de terceiros.

## Gerar o relatório

Na raiz do repositório:

```powershell
python scripts/discover_tse_catalog.py
python apps/analytics/generate_report.py
```

O relatório será gravado em `reports/catalog/index.html`. Abra esse arquivo diretamente no navegador. Se o manifesto ainda não existir, o gerador cria um relatório de estado pendente, sem inventar indicadores.

Também é possível informar caminhos:

```powershell
python apps/analytics/generate_report.py --manifest catalog/tse/datasets/manifest.json --output reports/catalog/index.html
```

## Servir via Docker

O serviço Analytics gera o relatório ao iniciar e o disponibiliza em `http://localhost:8501`. O diretório `catalog` é montado em modo somente leitura; o relatório é escrito no volume `reports`.

```powershell
docker compose up --build
```

## Conteúdo e limites

O relatório resume somente metadados CKAN: conjuntos, recursos, formatos e órgãos responsáveis. Não representa resultados eleitorais, votos, candidaturas, comparecimento ou abstenção.

Os valores são derivados dos arquivos JSON listados no manifesto local. O HTML contém CSS próprio, layout responsivo e estilo de impressão para salvar em PDF pelo navegador. Dados de origem são escapados antes de serem inseridos no documento.

## Arquitetura

- `apps/web`: interface principal Next.js e exploração do catálogo via API.
- `apps/analytics/generate_report.py`: geração de relatório HTML autônomo.
- `reports/catalog/index.html`: artefato gerado localmente; não é versionado.
- `services/api`: disponibilização dos metadados para a interface web.
