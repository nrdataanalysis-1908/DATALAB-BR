# Aplicação Streamlit

A aplicação em `apps/analytics` permite pesquisar e inspecionar os metadados do catálogo TSE gerado pelo coletor CKAN.

## Instalação e execução

```bash
python -m pip install -r apps/analytics/requirements.txt
python scripts/discover_tse_catalog.py
python -m streamlit run apps/analytics/app.py
```

A aplicação não cria indicadores eleitorais a partir de metadados. Se o manifesto não existir, informa como gerar o catálogo e não apresenta números fictícios. A pesquisa é textual e a exportação CSV contém apenas os registros filtrados carregados do manifesto.

## Roteiro de validação funcional

Após iniciar a aplicação, execute as verificações abaixo:

1. **Carga do catálogo:** confirme que a aplicação identifica o manifesto esperado e apresenta a quantidade de conjuntos e recursos efetivamente carregados.
2. **Estado vazio:** remova ou renomeie temporariamente o manifesto em um ambiente de teste e confirme que a interface orienta a executar a descoberta, sem preencher indicadores com valores artificiais.
3. **Filtros:** aplique filtros de organização, formato e texto; confirme que a tabela e os indicadores derivados refletem o mesmo subconjunto.
4. **Consistência:** compare a quantidade exibida na interface com a quantidade de linhas do conjunto filtrado exportado.
5. **Exportação:** gere o CSV e valide cabeçalhos, codificação, separador e conteúdo com um leitor independente.
6. **Regressão:** execute a suíte automatizada antes de publicar alterações.

## Comandos de verificação

Na raiz do repositório:

```bash
python -m pytest
python -m compileall -q src apps scripts
```

Para validar a interface localmente:

```bash
python -m streamlit run apps/analytics/app.py
```

A validação manual deve registrar o manifesto utilizado, os filtros aplicados e o resultado observado. Não use somente a abertura da página como evidência de consistência dos dados.

## Limites de interpretação

- Os gráficos e indicadores desta aplicação descrevem metadados do catálogo CKAN, não votos, candidaturas, comparecimento ou abstenção.
- A quantidade de recursos catalogados não equivale à quantidade de arquivos baixados, descompactados ou validados.
- A disponibilidade de um recurso no catálogo não comprova que seu conteúdo esteja íntegro ou que corresponda a um contrato de dados.
- Indicadores eleitorais só devem ser publicados após ingestão, validação do schema, tratamento de qualidade e documentação da granularidade e da fonte.
