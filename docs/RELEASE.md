# Promoção de release

Em Actions, executar **Promove release → Run workflow** e escolher `patch`
(padrão), `minor` ou `major`. A origem é sempre `integracao`.

## Fluxo

1. Calcula a próxima versão a partir da maior tag remota estável
   `vMAJOR.MINOR.PATCH`. De `v1.2.3`, patch gera `v1.2.4`, minor gera `v1.3.0`
   e major gera `v2.0.0`. Sem tags estáveis, usa `v0.0.0` como base.
2. Abre um PR de `integracao` para `main`, com a versão no título e o SHA da
   origem na descrição. Um PR já aberto entre essas branches impede outro
   disparo, sem editar ou substituir o PR existente.
3. Aguarda os três jobs da CI existente do PR. Não repete builds no workflow.
4. O GitHub Actions aprova o PR criado pela GitHub App, usando identidades
   diferentes. A App solicita auto-merge com **merge commit**, respeitando as regras
   do GitHub e o SHA capturado. Preserva os commits originais, sem rebase, squash ou bypass.
5. Quando o PR é integrado, a execução acionada por `pull_request: closed`
   publica a tag no `merge_commit_sha` desse PR e cria a **GitHub Release** com
   notas automáticas. PR fechado sem merge não publica versão.

O merge normal preserva os SHAs e os autores dos commits originais e adiciona
um commit de merge do PR em `main`. A App aparece como responsável pelo merge,
sem ser atribuída como autora dos commits originais. A tag e a GitHub Release
não criam um commit adicional de versão. O workflow não exclui nem reescreve
`integracao`.

## Configuração

- O workflow deve estar em `main` para permitir disparo manual e publicação
  após o merge. O helper `scripts/release/promote.py` deve estar em `integracao`.
- GitHub App instalada no repositório com **Contents: read/write**,
  **Pull requests: read/write** e **Workflows: write** para integrar alterações
  de workflows. Mantém a variável `RELEASE_APP_ID` e o secret
  `RELEASE_APP_PRIVATE_KEY`.
- Em Settings → General → Pull Requests, habilitar **Allow auto-merge** e
  **Allow merge commits**.
- Em Settings → Actions → General → Workflow permissions, habilitar
  **Allow GitHub Actions to create and approve pull requests**. O workflow
  solicita `pull-requests: write` somente no job de promoção.
- Proteções, reviews, checks e regras de `main` continuam aplicadas. Regras que
  exigem aprovação de Code Owners ou proíbem aprovação por bots podem exigir
  ação humana; não há fallback para ignorar essas regras. Conflitos ou merge
  recusado deixam o PR aberto e não geram Release.

A App cria e integra o PR para preservar os eventos normais da CI e do workflow
que publica a Release. A aprovação usa `GITHUB_TOKEN`, que não é o autor do PR.
A publicação usa `GITHUB_TOKEN` com `contents: write` no job de Release.

## Falhas e repetição

Uma falha de CI, aprovação ou auto-merge deixa o PR para inspeção. Se a origem
avançar depois da captura, o merge automático com aquele SHA será recusado;
feche o PR e inicie nova promoção. A publicação também rejeita metadados cujo
SHA não corresponda à origem efetivamente integrada.

A tag sempre aponta para o commit desse PR, mesmo se `main` avançar depois.
Se uma tag de mesmo nome apontar para outro commit, a publicação falha sem
sobrescrevê-la. Se a Release já existir para a tag correta, repetir o job é
seguro. Se a criação da Release falhar após o push da tag, repetir o job cria
somente a Release pendente. Não há atomicidade entre o merge, a tag e a API de
Releases; um merge concluído permanece em `main` mesmo se a API falhar.

A concurrency `promotion-main` serializa as execuções, sem cancelar uma
promoção em andamento. Outros escritores não são bloqueados.

## Deploy

O merge do PR atualiza `main` e segue as integrações Git existentes de Render e
Vercel. A criação da Release não executa outro deploy. O `render.yaml` mantém
`rootDir: backend`; filtros externos podem ignorar mudanças só de frontend.
A configuração dos provedores não foi alterada.

## Validação local

```bash
python -m unittest discover -s scripts/release -p 'test_*.py' -v
```

Os testes usam remotos bare temporários e respostas GitHub simuladas. Cobrem
versionamento, validação de PR integrado, origem/fork, avanço da origem, tag no
SHA integrado, duplicidade, falhas de autorização/persistência e repetição.
Não executar o workflow real para testar: ele pode integrar em `main` e iniciar
os deploys existentes.

Referências: [estratégias de merge no GitHub](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges),
[auto-merge no CLI](https://cli.github.com/manual/gh_pr_merge),
[GitHub Release e notas automáticas](https://cli.github.com/manual/gh_release_create).
