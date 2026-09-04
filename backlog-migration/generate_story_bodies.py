import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent

ISSUES_FILE = BASE_DIR / "input" / "issues.json"
MAP_FILE = BASE_DIR / "analysis" / "migration-map.json"
STORIES_DIR = BASE_DIR / "stories"


def load_json_file(path: Path):
    raw = path.read_bytes()

    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        text = raw.decode("utf-8")

    return json.loads(text)


def extract_field(body: str, field: str):
    pattern = rf"\|\s*{re.escape(field)}\s*\|\s*([^|]+)\|"
    match = re.search(pattern, body, flags=re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return None


def extract_eap_data(body: str):
    fields = [
        "ID EAP",
        "Pacote principal",
        "SP final",
        "Dependencias",
        "Responsavel",
        "Apoio",
        "Horas previstas",
        "Duracao em dias uteis",
        "Valor/hora",
        "Custo previsto",
        "Status planejado",
        "Observacoes",
    ]

    return {
        field: extract_field(body, field)
        for field in fields
        if extract_field(body, field)
    }


def slugify(value: str):
    value = value.lower()

    substitutions = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }

    for source, target in substitutions.items():
        value = value.replace(source, target)

    value = re.sub(r"\[[^\]]+\]", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")

    return value


def story_persona(title: str):
    lower = title.lower()
    if "página inicial" in lower or "home" in lower:
        return "usuário do sistema"

    if any(term in lower for term in [
        "usuário",
        "autenticar",
        "cliente",
    ]):
        return "usuário do sistema"

    if any(term in lower for term in [
        "funcionário",
        "nível de acesso",
        "auditoria",
    ]):
        return "administrador"

    if any(term in lower for term in [
        "obra",
        "exemplar",
        "acervo",
        "isbn",
        "autor",
        "título",
    ]):
        return "funcionário responsável pelo acervo"

    if any(term in lower for term in [
        "empréstimo",
        "devolução",
    ]):
        return "atendente"

    if any(term in lower for term in [
        "venda",
        "reserva",
    ]):
        return "atendente"

    if any(term in lower for term in [
        "notificação",
        "lembrete",
    ]):
        return "cliente"

    return "usuário do sistema"


def clean_goal(title: str):
    title = re.sub(r"^\[[A-Z]+\]\s*", "", title).strip()

    transformations = {
        r"^Cadastro de obras$":
            "cadastrar uma obra",

        r"^Cadastro de exemplares$":
            "cadastrar um exemplar",

        r"^Cadastro de funcionários$":
            "cadastrar um funcionário",

        r"^Cadastro de clientes$":
            "cadastrar um cliente",

        r"^Inativação de usuários$":
            "inativar um usuário",

        r"^Inativação de obras$":
            "inativar uma obra",

        r"^Busca por título$":
            "buscar obras por título",

        r"^Busca por autor$":
            "buscar obras por autor",

        r"^Busca por ISBN/código de barras$":
            "buscar itens por ISBN ou código de barras",

        r"^Consulta de disponibilidade$":
            "consultar a disponibilidade de uma obra ou exemplar",

        r"^Registro de empréstimo$":
            "registrar um empréstimo",

        r"^Registro de devolução$":
            "registrar uma devolução",

        r"^Validação da situação do cliente$":
            "validar a situação do cliente antes de uma operação",

        r"^Cálculo da data de devolução$":
            "calcular a data prevista de devolução",

        r"^Atualização do status do exemplar$":
            "atualizar o status de um exemplar",

        r"^Geração de comprovante digital$":
            "gerar um comprovante digital",

        r"^Visualizar acervos disponíveis na página inicial$":
            "visualizar os acervos disponíveis na página inicial",
    }

    for pattern, replacement in transformations.items():
        if re.fullmatch(pattern, title, flags=re.IGNORECASE):
            return replacement

    if title:
        return title[0].lower() + title[1:]

    return title

def story_benefit(goal: str):
    lower = goal.lower().strip()

    if lower == "cadastrar uma obra":
        return (
            "manter o catálogo do acervo atualizado "
            "e permitir sua posterior consulta"
        )

    if lower == "cadastrar um exemplar":
        return (
            "registrar uma unidade física da obra "
            "e controlar sua disponibilidade"
        )

    if lower == "cadastrar um funcionário":
        return (
            "permitir que o funcionário utilize o sistema "
            "conforme suas permissões"
        )

    if lower == "inativar um usuário":
        return (
            "impedir seu uso operacional sem remover "
            "o histórico associado"
        )

    if lower == "inativar uma obra":
        return (
            "retirá-la das operações ativas preservando "
            "seu histórico no sistema"
        )

    if lower == "buscar obras por título":
        return "localizar rapidamente uma obra no acervo"

    if lower == "buscar obras por autor":
        return "localizar obras relacionadas ao autor informado"

    if "isbn" in lower or "código de barras" in lower:
        return (
            "localizar rapidamente a obra ou exemplar "
            "a partir de um identificador"
        )

    if "consultar a disponibilidade" in lower:
        return (
            "saber se existem exemplares disponíveis "
            "para a operação desejada"
        )

    if lower == "registrar um empréstimo":
        return (
            "controlar a retirada temporária de um exemplar "
            "por um cliente"
        )

    if lower == "registrar uma devolução":
        return (
            "encerrar corretamente o empréstimo e atualizar "
            "a disponibilidade do exemplar"
        )

    if "página inicial" in lower:
        return (
            "acessar rapidamente os acervos disponíveis "
            "no sistema"
        )

    return (
        "executar essa funcionalidade de acordo com "
        "as regras de negócio do LibStock"
    )

def generate_user_story(entry, original_issue):
    title = entry["new_title"]
    persona = story_persona(title)
    goal = clean_goal(title)
    benefit = story_benefit(goal)

    eap = extract_eap_data(original_issue.get("body") or "")

    dependency = eap.get("Dependencias", "-")

    lines = []

    if entry.get("eap"):
        lines.append(
            f"<!-- libstock-eap-task: EAP-{entry['eap']} -->"
        )
        lines.append("")

    lines.extend([
        "## História de usuário",
        "",
        f"Como **{persona}**,",
        f"quero **{goal}**,",
        f"para **{benefit}**.",
        "",
        "## Contexto",
        "",
        f"Esta história deriva da issue #{entry['source_issue']} "
        f"e do planejamento original do projeto LibStock.",
        "",
        "O objetivo é transformar o pacote de trabalho original em uma "
        "entrega funcional verificável, mantendo a rastreabilidade com a EAP.",
        "",
        "## Critérios de aceitação",
        "",
        "- [ ] O fluxo principal deve estar disponível para o usuário autorizado.",
        "- [ ] Os dados obrigatórios devem ser validados.",
        "- [ ] Dados inválidos devem produzir resposta de erro adequada.",
        "- [ ] A operação não deve deixar dados inconsistentes.",
        "- [ ] O resultado da operação deve poder ser validado pelo usuário.",
        "",
        "## Regras de negócio",
        "",
        "- RN01 — A operação deve respeitar as regras existentes do domínio LibStock.",
        "- RN02 — Operações protegidas devem exigir usuário autenticado quando aplicável.",
        "- RN03 — Alterações persistentes devem manter consistência dos dados.",
        "",
        "## Dependências",
        "",
        f"- Dependências EAP: `{dependency}`",
        "",
        "## Escopo técnico esperado",
        "",
        "### Backend",
        "",
        "- [ ] Definir ou atualizar schemas.",
        "- [ ] Implementar camada de serviço.",
        "- [ ] Implementar ou atualizar repository.",
        "- [ ] Disponibilizar endpoint quando aplicável.",
        "- [ ] Implementar validações.",
        "- [ ] Implementar testes automatizados.",
        "",
        "### Frontend",
        "",
        "- [ ] Implementar interface quando aplicável.",
        "- [ ] Integrar com a API.",
        "- [ ] Validar entradas do usuário.",
        "- [ ] Exibir feedback de sucesso e erro.",
        "",
        "## Fora do escopo",
        "",
        "- Funcionalidades não previstas nesta história.",
        "- Alterações em outros módulos sem dependência direta.",
        "",
        "## Definition of Done",
        "",
        "- [ ] Critérios de aceitação atendidos.",
        "- [ ] Código revisado.",
        "- [ ] Testes automatizados passando.",
        "- [ ] Integração validada.",
        "- [ ] Documentação atualizada quando necessário.",
        "- [ ] PR aprovada e integrada.",
        "",
        "## Rastreabilidade",
        "",
        f"- Issue original: #{entry['source_issue']}",
        f"- Milestone planejado: {entry['milestone']}",
        f"- Prioridade planejada: {entry['priority']}",
        f"- Tamanho planejado: {entry['size']}",
        "",
    ])

    if eap:
        lines.extend([
            "<details>",
            "<summary>Dados originais da EAP</summary>",
            "",
            "| Campo | Valor |",
            "| --- | --- |",
        ])

        for field, value in eap.items():
            lines.append(f"| {field} | {value} |")

        lines.extend([
            "",
            "</details>",
            "",
        ])

    return "\n".join(lines)


def generate_technical(entry, original_issue):
    eap = extract_eap_data(original_issue.get("body") or "")

    lines = [
        "## Objetivo técnico",
        "",
        f"Executar o trabalho definido em **{entry['new_title']}**, "
        "preservando o contexto e as dependências do planejamento original.",
        "",
        "## Critérios de conclusão",
        "",
        "- [ ] Trabalho técnico implementado.",
        "- [ ] Evidências registradas.",
        "- [ ] Testes executados quando aplicável.",
        "- [ ] Documentação atualizada quando aplicável.",
        "- [ ] Revisão concluída.",
        "",
        "## Rastreabilidade",
        "",
        f"- Issue original: #{entry['source_issue']}",
        f"- Milestone: {entry['milestone']}",
        f"- Prioridade: {entry['priority']}",
        f"- Size: {entry['size']}",
        "",
    ]

    if eap:
        lines.extend([
            "## Dados originais da EAP",
            "",
            "| Campo | Valor |",
            "| --- | --- |",
        ])

        for field, value in eap.items():
            lines.append(f"| {field} | {value} |")

        lines.append("")

    return "\n".join(lines)


def generate_epic(entry, original_issue):
    lines = [
        "## Objetivo",
        "",
        f"Agrupar as histórias derivadas de **{entry['current_title']}**.",
        "",
        "## Histórias previstas",
        "",
    ]

    for child in entry.get("children", []):
        lines.append(f"- [ ] {child['title']}")

    lines.extend([
        "",
        "## Critério de conclusão",
        "",
        "- [ ] Todas as histórias filhas concluídas.",
        "",
        "## Rastreabilidade",
        "",
        f"- Issue original: #{entry['source_issue']}",
        f"- Milestone: {entry['milestone']}",
        "",
    ])

    return "\n".join(lines)


issues = load_json_file(ISSUES_FILE)
migration_map = load_json_file(MAP_FILE)

issues_by_number = {
    issue["number"]: issue
    for issue in issues
}


generated = 0


for entry in migration_map:
    action = entry["action"]

    if action == "keep":
        continue

    original_issue = issues_by_number[entry["source_issue"]]

    milestone_dir = STORIES_DIR / entry["milestone"]
    milestone_dir.mkdir(parents=True, exist_ok=True)

    if action == "split":
        epic_content = generate_epic(
            entry,
            original_issue,
        )

        epic_file = (
            milestone_dir
            / f"issue-{entry['source_issue']}-epic.md"
        )

        epic_file.write_text(
            epic_content,
            encoding="utf-8",
        )

        generated += 1

        for index, child in enumerate(
            entry.get("children", []),
            start=1,
        ):
            child_entry = {
                **entry,
                "new_title": child["title"],
                "type": "user-story",
            }

            child_content = generate_user_story(
                child_entry,
                original_issue,
            )

            slug = slugify(child["title"])

            child_file = (
                milestone_dir
                / (
                    f"issue-{entry['source_issue']}"
                    f"-child-{index}-{slug}.md"
                )
            )

            child_file.write_text(
                child_content,
                encoding="utf-8",
            )

            generated += 1

        continue

    if entry["type"] == "user-story":
        content = generate_user_story(
            entry,
            original_issue,
        )
    else:
        content = generate_technical(
            entry,
            original_issue,
        )

    filename = (
        f"issue-{entry['source_issue']}-"
        f"{slugify(entry['new_title'])}.md"
    )

    output_file = milestone_dir / filename

    output_file.write_text(
        content,
        encoding="utf-8",
    )

    generated += 1


print(f"{generated} arquivos gerados.")
print(f"Diretório: {STORIES_DIR}")