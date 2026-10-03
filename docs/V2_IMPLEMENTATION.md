# V2 — implementação a partir do Figma

Referência: [LibStock — UX V2](https://www.figma.com/design/gjM1ugpgfNOl5tjngzH65P/Libstock--1-?node-id=0-1).

Estado atual e revisão técnica: [V2_REVIEW.md](V2_REVIEW.md).

As seções abaixo registram os incrementos anteriores; a matriz da revisão substitui os status antigos.

## Incremento inicial: home e autenticação

Implementado no frontend em 03/10/2026:

- Fundo branco e cabeçalho verde escuro compartilhado entre as rotas.
- Home baseada no frame `3:65`, com banner de leitura, categorias vindas da API e cards horizontais.
- Busca global por título, autor, ISBN ou código de barras, encaminhada a `/explorar` por parâmetros de URL.
- Busca local da home preservada em uma área expansível.
- Card compartilhado entre a home e resultados da busca; capas dinâmicas, fallback para imagens indisponíveis e indicação Venda/Empréstimo/Esgotado.
- Layout compartilhado de login/cadastro baseado no frame `3:51`, preservando validação, feedback e autenticação existentes. A marca local foi reutilizada.
- Saída da conta no cabeçalho e navegação condicionada pelos papéis atuais.
- Recuperação da sessão em segundo plano: a home pública não espera o refresh; rotas privadas e de autenticação aguardam sua conclusão.
- Reutilização das respostas de destaques e categorias durante uma visita à home, evitando chamadas adicionais ao limpar a busca.
- Fallback de rotas SPA na Vercel, depois do encaminhamento `/api/*`.

Não foram acrescentadas operações simuladas de empréstimo, venda ou reserva. Os textos da home descrevem a consulta disponível; nomes e dados de pessoas do Figma não são copiados para produção.

## Mapa de requisitos

O estado abaixo é uma inspeção dos controllers, services e rotas disponíveis, não uma homologação de toda a V2.

| EAP | Situação observada | Próximo incremento |
| --- | --- | --- |
| 1.2.1–1.2.2 | Consulta, edição e inativação administrativa de usuários já existem | Revisar UX e homologar permissões |
| 1.2.3 | Controle de pendências não possui fluxo operacional completo | Definir aplicação, regularização, histórico e bloqueios |
| 1.2.4 | Inativação de obras sem fluxo completo | Implementar bloqueios e confirmação conforme complementos V2 |
| 1.2.5 | Inclusão de exemplares existe; gestão completa de quantidades pendente | Gestão por exemplar e auditoria |
| 1.2.6 | Conversão de destinação sem fluxo completo | Definir permissões e impedimentos transacionais |
| 1.2.7–1.2.8 | Disponibilidade e ofertas derivadas no catálogo; apresentação compartilhada neste incremento | Detalhes públicos da obra e homologação |
| 1.2.9–1.2.14 | Sem controllers/services completos de empréstimo e devolução | Situação do cliente, solicitação/retirada, prazo, comprovante e devolução |
| 1.2.15–1.2.18 | Sem controllers/services completos de venda | Validação, bloqueio didático e baixa atômica do estoque |
| 1.2.19–1.2.22 | Sem controllers/services completos de reserva de compra | Registro, elegibilidade, fila, atendimento e prazo |
| 1.2.23 | Suíte atual de acesso e usuários; novos testes para sessão recuperada | Homologação integral V2 |
| 1.2.24 | Testes existentes de acervo; fluxos V2 incompletos | Ampliar junto aos services e migrations |
| 1.2.25–1.2.27 | Operações V2 ainda não disponíveis | Testes transacionais e concorrência com cada incremento |

## Decisões de negócio necessárias para circulação

O Figma estabelece: obra e exemplar são entidades distintas, reserva da V2 é de compra e a venda de exemplar didático é bloqueada. Os complementos contêm recuperação de erros e confirmações a reutilizar.

Ainda é necessário estabelecer no contrato de negócio, antes dos respectivos services:

- Regra efetiva do prazo de empréstimo; a data de devolução deve ser calculada pelo sistema, sem copiar datas ilustrativas.
- Política de pendências, quem regulariza e seus efeitos na elegibilidade.
- Prazo de retirada da reserva, expiração/cancelamento e avanço da fila.
- Permissão para empréstimo direto no balcão: o próprio Figma marca essa proposta como condicional.
- Transições permitidas na conversão e inativação, preservando operações em andamento.

## Desempenho e hospedagem

A configuração local encaminha `/api/*` da Vercel para `libstock-gfc5.onrender.com`. `render.yaml` configura uma API FastAPI no Render. O plano efetivo e os tempos de produção não foram medidos.

Defeito confirmado no código anterior: o inicializador Angular aguardava a recuperação da sessão antes de renderizar qualquer rota. Isso amplificava qualquer demora da API mesmo para visitantes. O novo fluxo elimina essa dependência para a home pública, mantendo guards que aguardam a autenticação.

[Render documenta](https://render.com/docs/free#spinning-down-on-idle) que serviços Free suspendem após 15 minutos sem tráfego e podem levar cerca de um minuto para iniciar. Se esse for o plano utilizado, é uma hipótese relevante para a primeira chamada lenta, não uma causa confirmada pela inspeção local. A mudança de frontend não elimina o início lento da API nem acelera consultas no banco.

Melhorias sem migração de hospedagem: renderização pública independente, lazy loading das rotas já existente, reaproveitamento de respostas por visita e carregamento tardio das capas. A ilustração local original tem aproximadamente 1,7 MiB; otimizar sua codificação preservando o aspecto visual é uma oportunidade futura.

Antes de decidir por outra hospedagem gratuita, medir separadamente documento/assets, refresh, catálogo, consultas de banco e comportamento após inatividade. Não há garantia de eliminar cold starts de serviços gratuitos apenas mudando a configuração da Vercel.

## Validação

- Build Angular de produção passou, sem alerta de orçamento de CSS.
- 103 testes Angular passaram em ChromeHeadless, incluindo busca global, saída da conta e descarte de respostas de buscas antigas.
- Novos testes verificam restauração única, sessão sem cookie e espera pelos guards antes de permitir/redirecionar navegação.
- Nenhum backend ou esquema de banco foi alterado neste incremento; migrations e testes de backend não foram executados.
- Revisão no Chrome da home e login em desktop e em viewport de 390px; ambas apresentaram scrollWidth de 390px, sem transbordamento horizontal. A revisão usou dados de teste locais.
- Alterações locais; não publicadas.

## Ajuste do cabeçalho após revisão visual

A navegação do cliente passou a seguir as posições do frame de referência: marca, busca de 365px, Início, Explorar acervo, Meus empréstimos, Minhas reservas e conta. O item ativo usa peso de fonte, sem preenchimento. O critério da busca aparece ao focar o campo, preservando o contrato atual da API. O menu do nome contém Minha conta, Como funciona e Sair, e fecha com Escape ou clique fora. Os módulos pendentes de empréstimos e reservas são exibidos desabilitados, com indicação acessível de “em breve”; não apontam a rotas inexistentes. Gênero permanece acessível pelos chips da home, sem prometer busca textual por gênero no cabeçalho.

## Recorte atual — detalhes e solicitações

Este incremento substitui a navegação “Explorar acervo” descrita acima:

- A aba foi removida e `/explorar` redireciona à home para compatibilidade.
- A busca do cabeçalho apresenta os resultados na home; cards da home e das
  categorias oferecem “Ver detalhes” para `/livros/:id`.
- A página mostra capa, título, autor, categorias, ISBN e disponibilidade
  retornada por modalidade pela API pública.
- Accordions de empréstimo e venda expandem na própria página.
- Empréstimo recebe retirada, calcula prévia de devolução em um mês de calendário
  e persiste uma solicitação pendente. Compra recebe data pretendida de retirada
  e persiste a solicitação para finalização posterior no balcão.
- Sucesso é anunciado por snackbar após confirmação da API. Visitantes são
  encaminhados ao login com retorno para o livro.
- Consulta local permanece não configurada, por decisão explícita do usuário.
- Solicitações não retêm exemplar; fila, atendimento e conclusão das operações
  são próximos incrementos. A reserva de compra de exemplar indisponível ainda
  não integra este fluxo de solicitação de compra de exemplar disponível.

### Validação deste recorte

- Build Angular passou; 113 testes Angular passaram em ChromeHeadless.
- 33 testes focados de backend passaram.
- Upgrade, `alembic check`, downgrade e novo upgrade passaram no PostgreSQL
  temporário. A suíte completa nesse banco teve 178 testes aprovados, incluindo
  concorrência e rollback dos novos repositories; um teste existente exige um
  funcionário inicial no banco. O runner recebeu esse seed, mas a repetição foi
  recusada pelo usuário, portanto ainda não foi verificada.
- Migration `20261003_0011` aplicada ao banco da API local após confirmar que ele
  estava em `20260908_0010`. O endpoint local de detalhes da obra 1 respondeu
  com dois exemplares para empréstimo e um para compra.
- Alterações locais, sem commit, PR ou publicação.

## Acompanhamento do cliente e revisão de 03/10/2026

- `/meus-emprestimos` e `/minhas-reservas` estão conectadas a consultas `/me`, com identidade obtida do token.
- Solicitação de empréstimo permanece aguardando retirada até confirmação do funcionário. Empréstimos OPEN são ativos ou em atraso; devolvidos desaparecem.
- Compra disponível cria uma reserva NOTIFIED com exemplar comercial destinado ao cliente. Compra indisponível usa WAITING e posição calculada pelo backend.
- Exemplar destinado não é livre para outro cliente, mas a baixa física SOLD ocorre somente após a venda confirmada.
- As operações do funcionário possuem API; as telas e consultas operacionais do balcão ainda precisam ser implementadas.
- A revisão separou leitura do catálogo, solicitações do cliente e circulação do funcionário, centralizando calendário, elegibilidade e disponibilidade.
- A migration 0013 acrescenta proteção de exemplares destinados e auditoria de transições. As migrations 0011 e 0012 já aplicadas foram preservadas.
- Matriz dos 27 requisitos, pendências, arquivos, endpoints e roteiro de teste: [V2_REVIEW.md](V2_REVIEW.md).
