# Promoção de release

O workflow `.github/workflows/promote-release.yml` tem um único job, disparado
manualmente em Actions (**Promove release → Run workflow**), escolhendo `patch` (padrão), `minor` ou `major`, sem informar a versão completa.
Ele sempre usa a ponta remota de `integracao` como origem, mesmo quando o disparo
é feito selecionando `main` ou outra branch. Não modifica `integracao`.

## Fluxo

1. Consulta as tags remotas estáveis no formato `vMAJOR.MINOR.PATCH` e incrementa
   a maior versão numérica conforme a escolha: de `v1.2.9`, `patch` gera
   `v1.2.10`, `minor` gera `v1.3.0` e `major` gera `v2.0.0`. Os componentes
   inferiores são zerados. Sem tags estáveis, usa `v0.0.0` como base: `patch`
   gera `v0.0.1`, `minor` gera `v0.1.0` e `major` gera `v1.0.0`. Tags de pré-release ou de outros formatos
   não participam do cálculo. A versão é registrada na tag, sem alterar versões
   de pacotes ou da API.
2. Faz merge `--no-ff` de `integracao` para `main` no runner.
3. Cria uma tag anotada no commit resultante e publica `main` e tag com um único
   `git push --atomic`. Conflitos, ausência de novidades, avanço das branches,
   colisão de tag ou rejeição do servidor encerram a execução sem publicação parcial.

A CI continua independente, nos pushes e PRs de `integracao` e `main`.
A promoção não repete builds, não transporta candidatos por artifacts e não
consulta proteções/checks via API. O operador deve promover uma integração já
validada pela CI. As proteções do GitHub continuam aplicadas pelo servidor;
nenhum force push ou bypass é configurado pelo workflow.

## Configuração

- O workflow precisa estar em `main` (branch padrão) para permitir disparo manual.
  O helper `scripts/release/promote.py` deve estar em `integracao` antes da execução.
- Mantém a GitHub App existente, com variável `RELEASE_APP_ID` e secret
  `RELEASE_APP_PRIVATE_KEY`. Ela precisa de `Contents: read/write` e, para promover
  mudanças de workflows, `Workflows: write`. Não precisa das permissões de leitura
  de Administration, Checks ou Commit statuses usadas pelo preflight anterior.
- As proteções de `main` e das tags precisam permitir essa publicação direta.
  Se exigirem PR ou checks ausentes no commit de merge, o GitHub recusará o push.

A App mantém os eventos normais de push para a CI. O token padrão `GITHUB_TOKEN`
não dispara workflows de push gerados por ele, conforme a
[documentação do GitHub](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

O push em `main` segue as integrações Git já configuradas de Render e Vercel.
Não há hooks ou jobs adicionais de deploy. O resumo registra a versão e o commit
publicados; a conclusão dos deploys deve ser consultada nos provedores.
O `render.yaml` mantém `rootDir: backend`; os filtros do provedor podem ignorar
mudanças somente de frontend. A configuração externa não foi alterada.

A concurrency `promotion-main` serializa as execuções, sem cancelar uma promoção
em andamento. Escritores externos não são bloqueados: a release corresponde ao
SHA de `integracao` capturado, e commits que chegarem depois ficam para a próxima.

## Validação local

```bash
python -m unittest discover -s scripts/release -p 'test_*.py' -v
```

Os testes usam remotos bare temporários e não promovem branches reais.
Cobrem incremento de versão, merge/tag, conflitos, ausência de mudanças,
concorrência e rejeição atômica pelo servidor. Não disparar o workflow real para
testar: ele publica em `main` e pode iniciar os deploys.
