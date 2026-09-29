# Diretrizes do Projeto LibStock

## Fluxo de Git e Ramificação (Git Workflow)

Sempre que for desenvolver uma nova funcionalidade:
1. **Criação de Branch**: Criar uma branch a partir da branch `integracao` (ou da base atualizada) seguindo a convenção de nomenclatura `feature/<nome-da-feature>`.
2. **Desenvolvimento e Validação**: Realizar as alterações mantendo commits semânticos e verificando testes/builds.
3. **Pull Request**: Publicar a branch no repositório remoto e abrir um Pull Request direcionado para a branch `integracao`.
