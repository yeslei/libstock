# LibStock

## Stack
Python / FastAPI / SQLAlchemy / PostgreSQL.

## Arquitetura
Controller -> Service -> Repository -> SQLAlchemy.

## Regras
- não alterar migrations antigas;
- não inventar regras de negócio;
- não modificar arquivos fora do escopo;
- reutilizar padrões existentes;
- testes obrigatórios;
- uma feature por branch;
- antes de terminar, rodar testes e revisar diff.