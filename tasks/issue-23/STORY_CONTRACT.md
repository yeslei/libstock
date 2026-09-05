# Story Contract — Issue #23

## Identificação

- Issue: #23
- Título: [US] Busca por título
- Milestone: V1
- Prioridade: P0
- Tamanho: XS

## Objetivo

Permitir localizar obras a partir de parte do título informado.

## Entidade principal

`books`

## Contrato funcional

A busca deve:

1. receber um termo de título;
2. remover espaços no início e no fim;
3. rejeitar termo vazio;
4. realizar busca parcial por substring;
5. ser case-insensitive;
6. retornar apenas obras ativas;
7. retornar coleção vazia quando não houver correspondência;
8. não modificar dados.

## Fora do escopo

Não implementar:

- busca por autor;
- busca por ISBN;
- busca por barcode;
- disponibilidade;
- cadastro de obra;
- edição de obra;
- cadastro de exemplar;
- venda;
- empréstimo;
- reserva;
- paginação genérica;
- ordenação por relevância.

## Arquitetura

Seguir:

`controller -> service -> repository -> SQLAlchemy`

## Banco

Não criar migration.

O schema atual já possui:

- tabela `books`;
- coluna `title`;
- coluna `is_active`;
- índice para `title`.

## Critérios de aceite

- [ ] Busca por substring funciona.
- [ ] Busca é case-insensitive.
- [ ] Espaços externos são removidos.
- [ ] Termo vazio é rejeitado.
- [ ] Somente obras ativas são retornadas.
- [ ] Nenhuma correspondência retorna coleção vazia.
- [ ] A busca não modifica dados.
- [ ] Nenhuma migration é criada.
- [ ] Testes automatizados passam.

## Definition of Done

- [ ] schema implementado;
- [ ] repository implementado;
- [ ] service implementado;
- [ ] controller/router implementado;
- [ ] dependency wiring realizado quando necessário;
- [ ] rota registrada;
- [ ] testes passando;
- [ ] sem alterações fora do escopo.