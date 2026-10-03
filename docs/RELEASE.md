# Promoção de release

Issue: [#113](https://github.com/yeslei/libstock/issues/113).

O workflow `.github/workflows/promote-release.yml` promove `integracao` para
`main` após um disparo manual com versão SemVer, por exemplo `1.2.3` ou
`1.2.3-rc.1`. A tag correspondente é `v1.2.3`. Não abre PR de promoção.
Esta é a exceção aprovada para merge automático; o PR de implementação
continua direcionado a `integracao` e depende de revisão humana.

## Pré-requisitos de operação

1. O workflow deve estar registrado na branch padrão `main`, condição do GitHub
   para `workflow_dispatch`. O primeiro registro precisa de uma etapa
   administrada após a aceitação do PR de implementação, respeitando o processo
   de revisão e as proteções existentes. Esta tarefa não realizou esse registro,
   merge para `main`, tag, deploy ou disparo do workflow. Enquanto o arquivo não
   chegar à branch padrão, a promoção manual nova não estará disponível.
2. Uma GitHub App instalada somente nos repositórios necessários, com
   `Contents: read/write`, `Administration: read`, `Checks: read` e
   `Commit statuses: read`. Para promover commits que alteram `.github/workflows`,
   conceder também `Workflows: write`. Não conceder bypass de regras à App.
3. Configurar a variável de Actions `RELEASE_APP_ID` e o secret
   `RELEASE_APP_PRIVATE_KEY`. O token é criado apenas no job de publicação;
   builds e testes não recebem o token da App. Não existe fallback para
   `GITHUB_TOKEN` na publicação. O token padrão é usado com `contents: read`
   somente na leitura de refs da preparação, inclusive em repositório privado.
4. As políticas de `main` e das tags devem permitir o merge direto produzido
   pelo pipeline. Exigir PR, histórico linear, assinatura, fila de merge,
   restrição de atores ou outra regra incompatível causa recusa explícita,
   sem bypass. A implementação não altera proteções ou rulesets.
5. Confirmar nos provedores existentes: Render acompanhando `main` com
   auto deploy habilitado; Vercel com Production Branch `main` e integração Git
   automática habilitada. Não cadastrar um segundo hook ou workflow de deploy.
   Essas configurações externas e a instalação da App **não foram verificadas
   nem modificadas nesta implementação**.

O GitHub não dispara novos workflows de `push` quando a publicação usa o token
padrão `GITHUB_TOKEN`. A App permite os eventos normais do push sem introduzir
um dispatch adicional de CI ou deploy. A única CI existente é reutilizada para
as validações e continua atendendo pushes/PRs normalmente.

## Execução manual

Em Actions, selecionar **Promove release**, escolher exclusivamente a branch
`integracao` e fornecer a versão sem o prefixo `v`. O workflow rejeita outras
branches e versões inválidas. Não executar esse procedimento para testar a
implementação: o último job publica refs reais e pode iniciar deploys.

O workflow captura os SHAs de `integracao` e `main`, exige que a origem ainda
seja o SHA do disparo e prepara um merge `--no-ff` em checkout descartável.
Nenhuma ref remota é alterada na preparação. Se a origem já estiver contida
em `main`, o workflow recusa a promoção sem alterações.

A CI reutilizável valida separadamente o SHA exato de `integracao` e o commit
candidato, transportado por um Git bundle de artifact da mesma execução.
Ela executa as validações existentes: compilação/importação do backend e
build de produção do frontend; também executa os testes locais do helper de
release. Os jobs de validação não possuem token de escrita. O job de publicação
importa os objetos do bundle, mas executa apenas os helpers da origem oficial,
sem executar código do candidato com o token da App.

Depois das validações, o preflight consulta a proteção clássica de `main`,
regras ativas de branch, rulesets de tags (incluindo herdados) e checks exigidos.
Consultas paginadas ou indisponíveis não são tratadas como ausência de proteção.
Um 404 de proteção clássica só é aceito quando a metadata da branch confirma
`protected: false`. Regras desconhecidas também impedem publicação.

Essa recusa conservadora também pode bloquear uma branch protegida somente
por rulesets compatíveis: o GitHub informa `protected: true`, mas a consulta
de proteção clássica retorna 404. O pipeline não distingue esse caso de
permissão insuficiente e interrompe a promoção, sem bypass.

Os checks exigidos precisam ter sucesso tanto no SHA de origem quanto no SHA
candidato, incluindo a identidade da App quando fixada pela regra. Um build
local aprovado não equivale a um check registrado pelo GitHub. Como o candidato
não é publicado em uma branch intermediária, configurações com required checks
sem resultado nesse SHA impedirão a promoção. O pipeline recusa esse caso;
não publica refs intermediárias nem substitui as regras por um bypass.

Imediatamente antes de publicar, os SHAs remotos são consultados novamente.
Avanço detectado de qualquer branch exige um novo disparo manual. O helper cria
a tag anotada no candidato e usa um único `git push --atomic` com refspecs
explícitos para `main` e para essa tag. O commit resultante de `main` e a tag
são publicados juntos ou nenhum deles é publicado. Não há force push,
tentativa parcial ou fallback quando o servidor rejeita a publicação.

## Deploy e concorrência

O push de `main` é o único gatilho usado para as integrações Git já existentes
de Render/Vercel. Não há deploy hook, API de deploy, `repository_dispatch`
ou `workflow_dispatch` de deploy no novo pipeline. A tag identifica a release;
os provedores devem acompanhar a branch de produção, sem um segundo gatilho
de tag. O resumo de Actions registra tag e SHA publicados, mas não declara
sucesso do deploy: isso precisa ser confirmado nos provedores.

O `render.yaml` mantém `rootDir: backend`. Os filtros de auto deploy associados
ao diretório raiz podem ignorar commits que não mudam o backend; uma release
somente de frontend não garante um novo deploy do backend. Não alterar esse
comportamento durante a implementação do pipeline.

A concurrency `promotion-main`, sem cancelamento de execução em andamento,
serializa publicações deste workflow. Isso não bloqueia escritores externos:
as consultas de refs não constituem uma trava distribuída sobre `integracao`.
Se essa branch avançar entre a última consulta e o push, a release continua
representando apenas o SHA capturado e validado. O push normal protege `main`
contra atualizações que não sejam fast-forward, e as políticas do servidor
continuam sendo a autoridade final. Não há garantia de incluir commits novos
que chegaram depois da captura.

## Falhas e validação segura

- Versão inválida, branch ausente, tag existente, falta de mudanças, checkout
  sujo, conflito ou divergência durante fetch: preparação termina com erro.
- Build/teste malsucedido: o job de publicação não executa.
- App ausente, autenticação insuficiente, API indisponível, regra incompatível
  ou check exigido ausente/falho: preflight termina com erro.
- Corrida detectada, conflito de tag, rejeição de proteção ou servidor sem
  suporte a atomic push: nenhuma publicação parcial nem force push é tentada.
  Uma tag local pode permanecer no runner descartável após recusa remota.

Executar na raiz para testar sem rede e sem promoção real:

```bash
python -m unittest discover -s scripts/release -p 'test_*.py' -v
```

Os testes de Git criam remotos bare em diretórios temporários locais e cobrem
merge/tag, SemVer, conflito, duplicidade, ausência de mudanças, corrida,
adulteração do candidato e rejeição atômica de cada ref por hook de servidor.
Os testes de política usam respostas simuladas; não consultam APIs reais.
Não usar `promote.py prepare/publish` no checkout real como teste.

Referências oficiais: [workflow_dispatch](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#workflow_dispatch),
[eventos com tokens](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow),
[Git push atomic](https://git-scm.com/docs/git-push),
[Render auto deploy e diretório raiz](https://render.com/docs/monorepo-support),
[Vercel Git integrations](https://vercel.com/docs/git).
