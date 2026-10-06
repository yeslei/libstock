# Gestão do acervo

Fluxo de trabalho do vendedor, estoquista e administrador. A área de trabalho usa somente sidebar. A entrada pela raiz ou pelo painel antigo restaura a sessão e encaminha o funcionário ao balcão; as páginas de administração também usam esse layout.

## Organização

- **Acervo:** busca por título, autor, categoria, ISBN ou código do exemplar. Uma linha mostra título e autor, categoria e números disponíveis para empréstimo e venda. A linha inteira abre a obra, inclusive pelo teclado. Um seletor filtra o acervo completo; a paginação aparece quando necessária.
- **Obra:** caminho de volta explícito, capa quando disponível e números de estoque sem cards. Categoria e situação aparecem junto aos dados da obra. Editar dados, editar categorias e inativar ficam juntos abaixo da tabela. A edição de categorias tem cancelamento explícito.
- **Exemplares:** código, finalidade, condição, preço e situação. A tabela mostra cinco exemplares por página, sem coluna de ações. Selecionar o código abre um painel com edição, conversão, inativação/reativação e exclusão, respeitando os bloqueios existentes. Os motivos de bloqueio aparecem somente no painel selecionado.
- **Adicionar exemplares:** características comuns definidas uma vez, códigos gerados, leitura/digitação com Enter ou lista colada. Revisão do lote antes do cadastro; duplicidades detectadas; persistência atômica. ISBN identifica a obra, código identifica cada cópia física.
- **Circulação:** as operações existentes são acessíveis pela sidebar e preservam as regras da main. Cliente e exemplar continuam sendo escolhidos explicitamente, com confirmação e comprovante.

## Requisitos e limites

| Requisito | Comportamento |
|---|---|
| RF01 | Cadastro, edição bibliográfica e categorias, inativação e reativação, exemplares em lote e conversão com preço comercial obrigatório. |
| RF02 / RF06 | Venda de exemplar comercial livre; confirmação atualiza o estoque na mesma transação. |
| RF03 / RF04 | Empréstimo e devolução integrados aos exemplares e clientes, com disponibilidade atualizada. |
| RF05 | Disponibilidade real separada por finalidade, excluindo exemplares emprestados, reservados, vendidos, inativos e comprometidos. |
| RF07 | Reservas de compra e fila preservadas dos fluxos integrados da main. |
| RF08 | Alertas e estados na interface já existentes; envio automatizado por e-mail continua planejado. |

A destinação é obrigatória **por exemplar**, conforme o modelo vigente: uma obra pode ter cópias didáticas e comerciais. Categoria literária pertence à obra. Venda didática é bloqueada pelo backend; conversão exige exemplar livre e respeita reservas e solicitações pendentes. Estoque não é um número editável: cada entrada ou saída corresponde a um exemplar físico.

A inativação mantém código e histórico. Não é possível inativar exemplar em operação nem retirar o último exemplar ativo de uma obra ativa; a interface e a API informam os motivos. Reativação retorna exemplar elegível à disponibilidade. Operações continuam auditadas e serializadas pelo lock da obra.

Princípios aplicados: visibilidade do estado, reconhecimento de caminhos, prevenção de erros e recuperação contextual, baseados nas [heurísticas de usabilidade do Nielsen Norman Group](https://www.nngroup.com/articles/ten-usability-heuristics/). São decisões de implementação; não constituem avaliação ou aprovação dos autores citados pelo usuário.
