# Implementation Plan — Issue #23: Busca de obras por título

## 1. Scope
Implementar a funcionalidade de busca de obras (books) pelo título. A busca deve ser realizada na tabela `books` e retornar uma lista de obras que atendam ao critério.

## 2. Contract Summary
- **Objetivo:** Permitir que usuários encontrem livros pelo título.
- **Escopo:** Apenas busca textual no campo `title`.
- **Fora de escopo:** Busca por autor, ISBN ou outros campos; filtragem por disponibilidade de exemplares (copies); paginação (a confirmar).
- **Critérios de Aceite:**
    - Retornar lista de livros compatíveis.
    - Respeitar a arquitetura do projeto.
    - Validar entrada conforme definido pelo PO.

## 3. Existing Architecture Findings
O projeto utiliza FastAPI com uma arquitetura em camadas bem definida:
- **Controller:** Define rotas e lida com HTTP.
- **Service:** Contém a lógica de negócio e orquestração.
- **Repository:** Lida com o acesso ao banco de dados via SQLAlchemy.
- **Schema:** Pydantic models para validação e serialização.
- **Dependencies:** Injeção de dependência centralizada em `app/dependencies/`.

## 4. Domain Findings
O modelo `Book` em `backend/app/models/domain.py` possui:
- `title: Mapped[str] = mapped_column(String(255), nullable=False)`
- `is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))`
- Índice: `Index("idx_books_title", "title")`

## 5. Relevant Existing Files
- `backend/app/models/domain.py`: Definição do modelo `Book`.
- `backend/app/main.py`: Registro de routers.
- `backend/app/dependencies/services.py`: Provedores de serviços.

## 6. Files to Create
- `backend/app/repositories/book_repository.py`: Consultas à tabela `books`.
- `backend/app/services/book_service.py`: Lógica de validação e busca.
- `backend/app/controllers/book_controller.py`: Endpoint `GET /api/v1/books`.
- `backend/app/schemas/book_schema.py`: `BookSearchResponse` (e `BookSearchParams` se necessário).

## 7. Files to Modify
- `backend/app/main.py`: Adicionar `app.include_router(book_router)`.
- `backend/app/dependencies/services.py`: Adicionar `get_book_service`.

## 8. Proposed API Contract
`GET /api/v1/books?title={termo}`

**Resposta (200 OK):**
```json
[
  {
    "id": 1,
    "title": "Título do Livro",
    "author": "Nome do Autor",
    "is_active": true
  }
]
```

## 9. Repository Changes
Implementar `BookRepository.search_by_title(title: str)`:
- Utilizar `db.query(Book).filter(Book.title.ilike(f"%{title}%"))` (sujeito a confirmação do PO sobre o tipo de busca).

## 10. Service Changes
Implementar `BookService.search_books(title: str)`:
- Validar se `title` não é vazio ou apenas espaços.
- Aplicar regras de negócio (ex: filtrar apenas `is_active=True`?).

## 11. Controller Changes
Implementar `BookController`:
- Rota `GET /`.
- Injeção de `BookService`.

## 12. Schema Changes
Definir `BookResponse` em `book_schema.py`, baseando-se no `UserResponse`.

## 13. Dependency Injection Changes
Adicionar `get_book_service` em `backend/app/dependencies/services.py`.

## 14. Error Handling
- Retornar lista vazia `[]` se nada for encontrado (padrão REST).
- Validar erros de entrada (422 via FastAPI/Pydantic).

## 15. Authentication / Authorization
A definir: a busca é pública ou apenas para usuários autenticados? Padrão atual em `user_controller` exige `get_current_user`.

## 16. Test Strategy
- **Unitários:** Testar `BookService` com mock do repository (casos de borda: título vazio, espaços).
- **Integração:** Testar `BookRepository` com banco real (PostgreSQL) para validar o `ILIKE` e o uso do índice.
- **E2E:** Testar o endpoint via `TestClient`.

## 17. Implementation Order
1. Repository
2. Service
3. Schema
4. Controller & Dependency
5. Registro no `main.py`
6. Testes

## 18. Verification Commands
- `pytest backend/tests/` (quando houver testes)
- `ruff check .`
- `mypy .`

## 19. Open Decisions
| Tema | Decisão Pendente | Impacto |
| --- | --- | --- |
| Estratégia de Busca | `ILIKE` (contém), `LIKE` (exato), ou prefixo? | Performance/UX |
| Filtro de Atividade | Retornar inativos (`is_active=False`)? | Regra de Negócio |
| Autenticação | Requer login? | Segurança |
| Paginação | Limite de resultados? | Performance |

## 20. Risks
- Performance da busca `ILIKE %termo%` em bases grandes (o índice `idx_books_title` pode não ser usado eficientemente).
- Ambiguidade no critério de "título compatível".

## 21. Recommendation
**BLOCKED**

O plano técnico está sólido, mas a implementação depende de definições de negócio (Estratégia de Busca e Filtro de Atividade) que impactam diretamente a query e o contrato da API. Recomenda-se preencher o `STORY_CONTRACT.md` com estas decisões antes de iniciar.
