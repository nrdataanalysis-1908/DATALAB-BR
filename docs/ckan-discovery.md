# Descoberta do catálogo CKAN do TSE

O cliente usa a Action API pública do Portal de Dados Abertos do TSE. A descoberta consulta `package_search` em páginas, normaliza os metadados dos conjuntos e dos recursos e grava JSON local, sem baixar os arquivos de dados.

## Executar

Requer Python 3.10 ou superior. O cliente e os testes usam somente a biblioteca padrão; `pytest` é opcional para desenvolvimento.

```bash
python -m pip install -e ".[dev]"
python scripts/discover_tse_catalog.py
```

Opções disponíveis:

- `--base-url`: endereço base do portal CKAN.
- `--output`: diretório de saída (padrão: `catalog/tse/datasets`).
- `--page-size`: registros por página (1–1000; padrão: 100).
- `--timeout`: timeout HTTP em segundos.
- `--retries`: tentativas adicionais para falhas transitórias.
- `--log-level`: nível de log.

## Artefatos gerados

- Um arquivo JSON por conjunto, contendo metadados, licença declarada, grupos, tags e recursos.
- `manifest.json`, com contagem, caminhos e SHA-256 dos arquivos de metadados.
- `.ckan_checkpoint.json`, atualizado atomicamente após cada página para permitir retomada.

Os arquivos gerados ficam locais e não são versionados por padrão. A execução não baixa recursos nem valida a licença jurídica de redistribuição: preserva apenas os identificadores e títulos informados pelo CKAN. Confirme os metadados na fonte antes de redistribuir qualquer dado.

## Resiliência e segurança

O cliente aplica timeout, retry com backoff exponencial e jitter para falhas transitórias, valida o envelope `success` do CKAN e grava arquivos por substituição atômica. Slugs são validados antes de compor caminhos locais. Os testes usam respostas simuladas; a consulta real ao portal deve ser executada no ambiente de implantação para confirmar disponibilidade e contagem no momento da execução.

## API de referência

- [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/)
- [CKAN Action API — documentação oficial](https://docs.ckan.org/en/latest/api/)

## Integridade do manifesto e portabilidade

A descoberta só publica um novo `manifest.json` quando a paginação alcança o total remoto declarado e as páginas não apresentam lacunas. Uma página vazia antes do total esperado é tratada como resposta inconsistente: a execução falha e o manifesto completo anterior permanece preservado. O checkpoint da última página válida continua disponível para diagnóstico e retomada.

Os nomes dos conjuntos são mantidos como identificadores lógicos no manifesto. Para gravação local, slugs que colidiriam com nomes de dispositivos do Windows (por exemplo, `CON`, `NUL`, `COM1` e `LPT1`) ou terminariam em ponto recebem um nome de arquivo determinístico derivado de SHA-256. O mesmo mapeamento é usado na verificação do checkpoint, na gravação e no manifesto.

Os arquivos JSON são serializados em modo estrito. Valores numéricos não finitos (`NaN`, `Infinity` e `-Infinity`) são rejeitados, e campos textuais de grupos, tags e recursos passam por validação de tipo antes da normalização.

## Tipos dos metadados de recursos

Os campos textuais de cada recurso (`id`, `name`, `description`, `format`, `url`, `created`, `last_modified`, `hash` e `mimetype`) aceitam somente texto ou `null`. O tamanho deve ser um inteiro não negativo e `datastore_active` deve ser booleano ou `null`. Um recurso com tipo incompatível é ignorado como metadado malformado, sem interromper a descoberta dos demais conjuntos.