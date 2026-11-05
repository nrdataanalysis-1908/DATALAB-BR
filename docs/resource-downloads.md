# Download de recursos CKAN

O pipeline consome os metadados JSON gerados por \`discover_tse_catalog.py\` e baixa os recursos para a área local de landing. Não transforma nem extrai arquivos nesta etapa.

## Execução

\`\`\`bash
python -m pip install -e ".[dev]"
python scripts/discover_tse_catalog.py
python scripts/download_tse_resources.py
\`\`\`

Opções:

- \`--catalog\`: diretório dos metadados CKAN.
- \`--output\`: destino dos arquivos (padrão: \`data/landing/tse\`).
- \`--manifest\`: caminho opcional para o manifesto.
- \`--timeout\` e \`--retries\`: timeout por requisição e tentativas adicionais.

## Retomada e integridade

- Downloads incompletos permanecem como \`.part\`; o estado auxiliar registra URL e ETag.
- A retomada usa \`Range\` + \`If-Range\` e só acrescenta bytes quando o servidor confirma HTTP 206 e um \`Content-Range\` compatível.
- Se o servidor ignorar Range, a resposta HTTP 200 substitui o parcial e reinicia o download.
- O tamanho recebido é comparado ao \`Content-Length\`, quando fornecido.
- SHA-256 é calculado em streaming após a transferência. Um checksum esperado pode ser fornecido programaticamente com algoritmo explícito.
- O arquivo final só é publicado por rename atômico após a validação do checksum.
- O manifesto é atualizado atomicamente após cada recurso e registra sucessos e falhas. Uma nova execução pode retomar arquivos parciais.

O campo CKAN \`hash\` é preservado no catálogo, mas não é presumido como SHA-256: sua semântica/algoritmo varia conforme o publicador. Por segurança, o pipeline calcula SHA-256 próprio e só compara checksums externos quando algoritmo e valor esperado forem informados explicitamente.

## Limites operacionais

O downloader aceita somente URLs absolutas HTTP(S), sanitiza nomes de arquivo, valida timeout/backoff finitos, contadores inteiros e a configuração do checksum antes de iniciar a rede. Nomes são reservados por identificador no manifesto: colisões após sanitização (inclusive diferenças apenas de maiúsculas/minúsculas), conflitos entre execuções e tentativas de sobrescrever o próprio manifesto são rejeitados. O mesmo identificador pode atualizar seu arquivo já registrado. Os arquivos são dados externos não confiáveis; não abra nem extraia automaticamente os downloads. A extração segura será uma etapa separada com limites de tamanho, caminhos e tipos de entrada.

Os testes automatizados usam respostas HTTP simuladas. A validação de rede contra o portal deve ocorrer em ambiente com acesso à internet e deve ser feita inicialmente sobre um conjunto pequeno de recursos.
