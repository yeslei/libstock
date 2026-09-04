#!/usr/bin/env python3
"""
LibStock - migração das Issues via GitHub REST API.

Este script NÃO usa GitHub Projects v2 e NÃO depende de GraphQL.

Ele migra:
- KEEP    -> milestone da Issue existente
- REWRITE -> título + body + milestone da Issue existente
- SPLIT   -> Issue original vira EPIC + children são criadas/reutilizadas
             + vínculo parent/sub-issue via REST

Ele preserva:
- número das Issues originais
- estado open/closed das Issues existentes
- labels/assignees/comentários das Issues existentes
- rastreabilidade da EAP contida nos bodies gerados

Arquivos esperados:

backlog-migration/
├── migrate_issues_rest.py
├── analysis/
│   ├── migration-map.json
│   ├── issues-rest-migration-state.json   # criado automaticamente
│   └── issues-rest-migration-result.json  # criado automaticamente
└── stories/
    ├── V1/
    ├── V2/
    └── V3/

Uso:

    python migrate_issues_rest.py --dry-run
    python migrate_issues_rest.py --apply

Filtros:

    python migrate_issues_rest.py --milestone V1 --dry-run
    python migrate_issues_rest.py --issue 16 --dry-run
    python migrate_issues_rest.py --issue 16 --apply

Para continuar após erro:

    python migrate_issues_rest.py --apply --continue-on-error

Atraso entre mutations REST (proteção contra secondary rate limit):

    python migrate_issues_rest.py --apply --delay 1.0

Observação:
Priority, Size e Status do GitHub Project NÃO são tratados aqui.
Use um segundo script de sincronização do Project depois.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional


# ============================================================================
# Configuração
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent

REPO = "yeslei/libstock"
OWNER = "yeslei"
REPO_NAME = "libstock"

MAP_FILE = BASE_DIR / "analysis" / "migration-map.json"
STATE_FILE = BASE_DIR / "analysis" / "issues-rest-migration-state.json"
RESULT_FILE = BASE_DIR / "analysis" / "issues-rest-migration-result.json"
STORIES_DIR = BASE_DIR / "stories"

VALID_MILESTONES = ("V1", "V2", "V3")

# Já confirmados no repositório.
MILESTONE_NUMBERS = {
    "V1": 1,
    "V2": 2,
    "V3": 3,
}

# Header recomendado pela REST API.
API_HEADERS = [
    "-H",
    "Accept: application/vnd.github+json",
    "-H",
    "X-GitHub-Api-Version: 2022-11-28",
]


# ============================================================================
# Erros / IO
# ============================================================================

class MigrationError(RuntimeError):
    pass


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise MigrationError(f"Arquivo não encontrado: {path}")

    raw = path.read_bytes()

    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        text = raw.decode("utf-8")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MigrationError(f"JSON inválido em {path}: {exc}") from exc


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ============================================================================
# Execução de comandos
# ============================================================================

def run(
    cmd: list[str],
    *,
    input_text: Optional[str] = None,
) -> str:
    proc = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.returncode != 0:
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        raise MigrationError(
            "Falha: "
            + " ".join(cmd)
            + (f"\nstdout:\n{stdout}" if stdout else "")
            + (f"\nstderr:\n{stderr}" if stderr else "")
        )

    return (proc.stdout or "").strip()


def run_json(
    cmd: list[str],
    *,
    input_data: Any = None,
) -> Any:
    input_text = None

    if input_data is not None:
        input_text = json.dumps(
            input_data,
            ensure_ascii=False,
        )

    text = run(
        cmd,
        input_text=input_text,
    )

    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MigrationError(
            "Comando não retornou JSON válido:\n"
            + " ".join(cmd)
            + f"\nResposta:\n{text}"
        ) from exc


def gh_api_json(
    method: str,
    endpoint: str,
    *,
    payload: Any = None,
) -> Any:
    cmd = [
        "gh",
        "api",
        "--method",
        method,
        *API_HEADERS,
        endpoint,
    ]

    if payload is not None:
        cmd += [
            "--input",
            "-",
        ]

    return run_json(
        cmd,
        input_data=payload,
    )


def gh_api_get_paginated(endpoint: str) -> list[dict[str, Any]]:
    """
    Usa `gh api --paginate --slurp` para obter uma única lista JSON.

    Cada página da API é uma lista; --slurp produz lista de páginas.
    Em seguida achatamos.
    """
    data = run_json([
        "gh",
        "api",
        "--paginate",
        "--slurp",
        *API_HEADERS,
        endpoint,
    ])

    if data is None:
        return []

    if not isinstance(data, list):
        raise MigrationError(
            f"Resposta paginada inesperada para {endpoint}"
        )

    result: list[dict[str, Any]] = []

    for page in data:
        if not isinstance(page, list):
            raise MigrationError(
                f"Página REST inesperada para {endpoint}: {type(page)}"
            )
        result.extend(page)

    return result


# ============================================================================
# GitHub REST - leitura
# ============================================================================

def check_auth() -> None:
    run(["gh", "auth", "status"])


def validate_milestones() -> dict[str, dict[str, Any]]:
    milestones = gh_api_get_paginated(
        f"repos/{REPO}/milestones?state=all&per_page=100"
    )

    by_number = {
        int(item["number"]): item
        for item in milestones
        if item.get("number") is not None
    }

    result: dict[str, dict[str, Any]] = {}

    for key, number in MILESTONE_NUMBERS.items():
        milestone = by_number.get(number)

        if milestone is None:
            raise MigrationError(
                f"Milestone {key} esperado como #{number}, "
                "mas não foi encontrado."
            )

        title = str(milestone.get("title") or "")

        if not (
            title == key
            or title.startswith(f"{key} -")
            or title.startswith(f"{key} –")
        ):
            raise MigrationError(
                f"Milestone #{number} não parece ser {key}: `{title}`"
            )

        result[key] = milestone

    return result


def load_repo_issues() -> dict[int, dict[str, Any]]:
    """
    Endpoint /issues também retorna PRs. Eles são removidos.
    """
    items = gh_api_get_paginated(
        f"repos/{REPO}/issues?state=all&per_page=100"
    )

    result: dict[int, dict[str, Any]] = {}

    for item in items:
        if "pull_request" in item:
            continue

        number = item.get("number")

        if number is None:
            continue

        result[int(number)] = item

    return result


def get_subissues(parent_number: int) -> list[dict[str, Any]]:
    return gh_api_get_paginated(
        f"repos/{REPO}/issues/{parent_number}/sub_issues?per_page=100"
    )


# ============================================================================
# Migration map / stories
# ============================================================================

def validate_migration_map(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise MigrationError(
            "analysis/migration-map.json deve conter uma lista."
        )

    seen: set[int] = set()

    for entry in data:
        number = entry.get("source_issue")
        action = str(entry.get("action") or "").lower()
        milestone = entry.get("milestone")

        if not isinstance(number, int):
            raise MigrationError(
                f"source_issue inválido: {number!r}"
            )

        if number in seen:
            raise MigrationError(
                f"Issue duplicada no migration-map: #{number}"
            )

        seen.add(number)

        if action not in {"keep", "rewrite", "split"}:
            raise MigrationError(
                f"Ação inválida em #{number}: {action!r}"
            )

        if milestone not in VALID_MILESTONES:
            raise MigrationError(
                f"Milestone inválido em #{number}: {milestone!r}"
            )

        entry["action"] = action

        if action in {"rewrite", "split"}:
            if not entry.get("new_title"):
                raise MigrationError(
                    f"new_title ausente em #{number}"
                )

        if action == "split":
            children = entry.get("children")

            if not isinstance(children, list) or not children:
                raise MigrationError(
                    f"SPLIT #{number} não possui children."
                )

            for index, child in enumerate(children, start=1):
                if not child.get("title"):
                    raise MigrationError(
                        f"Child {index} de #{number} sem title."
                    )

    return data


def find_story_file(
    issue_number: int,
    milestone: str,
    kind: str,
    child_index: Optional[int] = None,
) -> Path:
    folder = STORIES_DIR / milestone

    if not folder.exists():
        raise MigrationError(
            f"Pasta inexistente: {folder}"
        )

    if kind == "normal":
        files = [
            p
            for p in folder.glob(f"issue-{issue_number}-*.md")
            if "-child-" not in p.name
            and "epic" not in p.name.lower()
        ]

    elif kind == "epic":
        files = list(
            folder.glob(f"issue-{issue_number}-*epic*.md")
        )

    elif kind == "child":
        if child_index is None:
            raise MigrationError(
                "child_index é obrigatório para kind=child."
            )

        files = list(
            folder.glob(
                f"issue-{issue_number}-child-{child_index}-*.md"
            )
        )

    else:
        raise MigrationError(
            f"Tipo de arquivo inválido: {kind}"
        )

    files = sorted(set(files))

    if len(files) != 1:
        raise MigrationError(
            f"Esperado exatamente 1 arquivo para "
            f"#{issue_number} ({kind}) em {folder}; "
            f"encontrados {len(files)}: {files}"
        )

    path = files[0]

    text = path.read_text(
        encoding="utf-8"
    ).strip()

    if not text:
        raise MigrationError(
            f"Arquivo Markdown vazio: {path}"
        )

    return path


def get_desired_body_file(
    entry: dict[str, Any],
) -> Optional[Path]:
    number = entry["source_issue"]
    milestone = entry["milestone"]

    if entry["action"] == "rewrite":
        return find_story_file(
            number,
            milestone,
            "normal",
        )

    if entry["action"] == "split":
        return find_story_file(
            number,
            milestone,
            "epic",
        )

    return None


def prevalidate_all_story_files(
    entries: list[dict[str, Any]],
) -> None:
    """
    IMPORTANTÍSSIMO:
    Valida TODOS os Markdown antes de executar a primeira mutation.
    Evita o incidente de body vazio quando arquivo não existe.
    """
    errors: list[str] = []

    for entry in entries:
        number = entry["source_issue"]
        milestone = entry["milestone"]

        try:
            if entry["action"] == "rewrite":
                find_story_file(
                    number,
                    milestone,
                    "normal",
                )

            elif entry["action"] == "split":
                find_story_file(
                    number,
                    milestone,
                    "epic",
                )

                for index, _child in enumerate(
                    entry.get("children", []),
                    start=1,
                ):
                    find_story_file(
                        number,
                        milestone,
                        "child",
                        index,
                    )

        except Exception as exc:
            errors.append(str(exc))

    if errors:
        raise MigrationError(
            "Falha na pré-validação dos Markdown:\n- "
            + "\n- ".join(errors)
        )


# ============================================================================
# Comparação de estado
# ============================================================================

def normalize_text(value: Optional[str]) -> str:
    return (
        (value or "")
        .replace("\r\n", "\n")
        .strip()
    )


def current_milestone_number(
    issue: dict[str, Any],
) -> Optional[int]:
    milestone = issue.get("milestone")

    if not milestone:
        return None

    try:
        return int(milestone["number"])
    except (KeyError, TypeError, ValueError):
        return None


def issue_update_plan(
    issue: dict[str, Any],
    entry: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """
    Gera SOMENTE os campos que realmente precisam mudar.
    Isso reduz requests e evita alterações desnecessárias.
    """
    payload: dict[str, Any] = {}
    reasons: list[str] = []

    desired_milestone = MILESTONE_NUMBERS[
        entry["milestone"]
    ]

    if current_milestone_number(issue) != desired_milestone:
        payload["milestone"] = desired_milestone
        reasons.append("milestone")

    if entry["action"] != "keep":
        desired_title = entry["new_title"]

        if str(issue.get("title") or "") != desired_title:
            payload["title"] = desired_title
            reasons.append("title")

        body_file = get_desired_body_file(entry)
        desired_body = body_file.read_text(encoding="utf-8")

        if normalize_text(issue.get("body")) != normalize_text(desired_body):
            payload["body"] = desired_body
            reasons.append("body")

    return payload, reasons


# ============================================================================
# REST - mutations
# ============================================================================

def sleep_after_write(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)


def patch_issue(
    issue_number: int,
    payload: dict[str, Any],
    *,
    delay: float,
) -> dict[str, Any]:
    result = gh_api_json(
        "PATCH",
        f"repos/{REPO}/issues/{issue_number}",
        payload=payload,
    )

    sleep_after_write(delay)

    if not isinstance(result, dict):
        raise MigrationError(
            f"PATCH #{issue_number} retornou resposta inesperada."
        )

    return result


def create_issue(
    *,
    title: str,
    body: str,
    milestone_number: int,
    delay: float,
) -> dict[str, Any]:
    result = gh_api_json(
        "POST",
        f"repos/{REPO}/issues",
        payload={
            "title": title,
            "body": body,
            "milestone": milestone_number,
        },
    )

    sleep_after_write(delay)

    if not isinstance(result, dict):
        raise MigrationError(
            f"Criação de `{title}` retornou resposta inesperada."
        )

    if result.get("number") is None or result.get("id") is None:
        raise MigrationError(
            f"Criação de `{title}` não retornou number/id."
        )

    return result


def add_subissue(
    *,
    parent_number: int,
    child_issue_id: int,
    delay: float,
) -> dict[str, Any]:
    result = gh_api_json(
        "POST",
        f"repos/{REPO}/issues/{parent_number}/sub_issues",
        payload={
            "sub_issue_id": child_issue_id,
        },
    )

    sleep_after_write(delay)

    if not isinstance(result, dict):
        raise MigrationError(
            f"Falha ao vincular sub-issue ao parent #{parent_number}."
        )

    return result


# ============================================================================
# Children / split
# ============================================================================

def exact_issue_by_title(
    repo_issues: dict[int, dict[str, Any]],
    title: str,
) -> Optional[dict[str, Any]]:
    matches = [
        issue
        for issue in repo_issues.values()
        if str(issue.get("title") or "").strip() == title.strip()
    ]

    if len(matches) > 1:
        numbers = ", ".join(
            f"#{item['number']}"
            for item in matches
        )

        raise MigrationError(
            f"Mais de uma Issue possui o título exato "
            f"`{title}`: {numbers}"
        )

    return matches[0] if matches else None


def child_update_plan(
    child_issue: dict[str, Any],
    *,
    desired_title: str,
    desired_body: str,
    desired_milestone: int,
) -> tuple[dict[str, Any], list[str]]:
    payload: dict[str, Any] = {}
    reasons: list[str] = []

    if str(child_issue.get("title") or "") != desired_title:
        payload["title"] = desired_title
        reasons.append("title")

    if normalize_text(child_issue.get("body")) != normalize_text(desired_body):
        payload["body"] = desired_body
        reasons.append("body")

    if current_milestone_number(child_issue) != desired_milestone:
        payload["milestone"] = desired_milestone
        reasons.append("milestone")

    return payload, reasons


def create_or_reuse_child(
    *,
    parent_entry: dict[str, Any],
    child_definition: dict[str, Any],
    child_index: int,
    repo_issues: dict[int, dict[str, Any]],
    state: dict[str, Any],
    apply: bool,
    delay: float,
) -> dict[str, Any]:
    parent_number = parent_entry["source_issue"]
    state_key = f"{parent_number}:{child_index}"
    desired_title = child_definition["title"]

    child_file = find_story_file(
        parent_number,
        parent_entry["milestone"],
        "child",
        child_index,
    )

    desired_body = child_file.read_text(
        encoding="utf-8"
    )

    desired_milestone = MILESTONE_NUMBERS[
        parent_entry["milestone"]
    ]

    children_state = state.setdefault(
        "children",
        {},
    )

    child_issue: Optional[dict[str, Any]] = None
    source = None

    # 1. Checkpoint local
    saved = children_state.get(state_key)

    if saved:
        try:
            saved_number = int(saved["number"])
        except (KeyError, TypeError, ValueError):
            saved_number = None

        if saved_number is not None:
            child_issue = repo_issues.get(saved_number)

            if child_issue is not None:
                source = "state"

    # 2. Fallback por título exato
    if child_issue is None:
        child_issue = exact_issue_by_title(
            repo_issues,
            desired_title,
        )

        if child_issue is not None:
            source = "title"

    created = False
    changed = False

    if child_issue is None:
        print(
            f"  child {child_index}: CREATE "
            f"{desired_title}"
        )

        if apply:
            child_issue = create_issue(
                title=desired_title,
                body=desired_body,
                milestone_number=desired_milestone,
                delay=delay,
            )

            repo_issues[
                int(child_issue["number"])
            ] = child_issue

            created = True
            changed = True

        else:
            child_issue = {
                "number": None,
                "id": None,
                "title": desired_title,
                "html_url": None,
            }

    else:
        number = child_issue["number"]

        print(
            f"  child {child_index}: REUSE "
            f"#{number} ({source})"
        )

        payload, reasons = child_update_plan(
            child_issue,
            desired_title=desired_title,
            desired_body=desired_body,
            desired_milestone=desired_milestone,
        )

        if payload:
            print(
                "    atualizar: "
                + ", ".join(reasons)
            )

            if apply:
                child_issue = patch_issue(
                    int(number),
                    payload,
                    delay=delay,
                )

                repo_issues[
                    int(number)
                ] = child_issue

            changed = True
        else:
            print("    conteúdo/milestone: SKIP")

    # Dry-run de child que ainda não existe:
    # não é possível verificar vínculo REST sem um ID real.
    if not apply and child_issue.get("number") is None:
        print(
            f"    parent #{parent_number}: "
            "será vinculado após criação"
        )

        return {
            "index": child_index,
            "title": desired_title,
            "number": None,
            "created": True,
            "changed": True,
            "parent_link_changed": True,
        }

    child_number = int(child_issue["number"])
    child_id = int(child_issue["id"])

    # Verifica vínculo parent/sub-issue via REST.
    current_subissues = get_subissues(parent_number)

    linked_ids = {
        int(item["id"])
        for item in current_subissues
        if item.get("id") is not None
    }

    parent_link_changed = child_id not in linked_ids

    if parent_link_changed:
        print(
            f"    vincular #{child_number} "
            f"como sub-issue de #{parent_number}"
        )

        if apply:
            add_subissue(
                parent_number=parent_number,
                child_issue_id=child_id,
                delay=delay,
            )
    else:
        print(
            f"    parent #{parent_number}: SKIP"
        )

    if apply:
        children_state[state_key] = {
            "number": child_number,
            "id": child_id,
            "url": (
                child_issue.get("html_url")
                or f"https://github.com/{REPO}/issues/{child_number}"
            ),
            "title": desired_title,
            "parent": parent_number,
        }

        save_json(
            STATE_FILE,
            state,
        )

    return {
        "index": child_index,
        "title": desired_title,
        "number": child_number,
        "created": created,
        "changed": changed,
        "parent_link_changed": parent_link_changed,
    }


# ============================================================================
# Resultado / validação final
# ============================================================================

def save_result(
    *,
    mode: str,
    results: list[dict[str, Any]],
    errors: int,
) -> None:
    save_json(
        RESULT_FILE,
        {
            "mode": mode,
            "repo": REPO,
            "processed": len(results),
            "errors": errors,
            "results": results,
        },
    )


def validate_final_state(
    entries: list[dict[str, Any]],
) -> list[str]:
    """
    Reconsulta via REST e faz auditoria objetiva.
    """
    fresh_issues = load_repo_issues()
    errors: list[str] = []

    for entry in entries:
        number = entry["source_issue"]
        issue = fresh_issues.get(number)

        if issue is None:
            errors.append(
                f"#{number}: Issue não encontrada após migração."
            )
            continue

        expected_milestone = MILESTONE_NUMBERS[
            entry["milestone"]
        ]

        if current_milestone_number(issue) != expected_milestone:
            errors.append(
                f"#{number}: milestone esperado "
                f"{expected_milestone}, encontrado "
                f"{current_milestone_number(issue)}."
            )

        if entry["action"] != "keep":
            if issue.get("title") != entry["new_title"]:
                errors.append(
                    f"#{number}: título divergente."
                )

            body_file = get_desired_body_file(entry)
            expected_body = body_file.read_text(encoding="utf-8")

            if normalize_text(issue.get("body")) != normalize_text(expected_body):
                errors.append(
                    f"#{number}: body divergente."
                )

        if entry["action"] == "split":
            subissues = get_subissues(number)
            subissue_numbers = {
                int(item["number"])
                for item in subissues
                if item.get("number") is not None
            }

            for index, child in enumerate(
                entry.get("children", []),
                start=1,
            ):
                match = exact_issue_by_title(
                    fresh_issues,
                    child["title"],
                )

                if match is None:
                    errors.append(
                        f"#{number} child {index}: "
                        "Issue não encontrada."
                    )
                    continue

                if int(match["number"]) not in subissue_numbers:
                    errors.append(
                        f"#{number} child {index}: "
                        "Issue existe, mas não está vinculada como sub-issue."
                    )

    return errors


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migra as Issues do backlog LibStock "
            "usando somente GitHub REST API."
        )
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida e exibe mudanças sem alterar o GitHub.",
    )

    mode.add_argument(
        "--apply",
        action="store_true",
        help="Aplica as mudanças no GitHub.",
    )

    parser.add_argument(
        "--milestone",
        choices=[
            "V1",
            "V2",
            "V3",
            "all",
        ],
        default="all",
        help="Filtra por milestone. Padrão: all.",
    )

    parser.add_argument(
        "--issue",
        type=int,
        help="Processa somente uma Issue.",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continua após erro em uma Issue.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help=(
            "Segundos entre mutations REST. "
            "Padrão: 1.0."
        ),
    )

    parser.add_argument(
        "--skip-final-validation",
        action="store_true",
        help=(
            "Não executa auditoria REST ao final do --apply."
        ),
    )

    args = parser.parse_args()
    apply = bool(args.apply)

    if args.delay < 0:
        print(
            "ERRO: --delay não pode ser negativo.",
            file=sys.stderr,
        )
        return 2

    try:
        check_auth()

        migration_map = validate_migration_map(
            load_json(MAP_FILE)
        )

        selected = [
            entry
            for entry in migration_map
            if (
                (
                    args.milestone == "all"
                    or entry["milestone"] == args.milestone
                )
                and (
                    args.issue is None
                    or entry["source_issue"] == args.issue
                )
            )
        ]

        if not selected:
            print("Nenhuma Issue selecionada.")
            return 1

        # 1. Valida todos os arquivos ANTES de qualquer mutation.
        prevalidate_all_story_files(selected)

        # 2. Valida milestones por REST.
        milestones = validate_milestones()

        # 3. Carrega todas as Issues por REST.
        repo_issues = load_repo_issues()

        state = load_json(
            STATE_FILE,
            default={
                "children": {}
            },
        )

        print("=" * 78)
        print("LIBSTOCK - MIGRAÇÃO DE ISSUES VIA REST")
        print("=" * 78)

        print(
            f"Modo={'APPLY' if apply else 'DRY-RUN'} "
            f"| cards={len(selected)} "
            f"| delay={args.delay}s"
        )

        print("GraphQL: NÃO UTILIZADO")
        print("GitHub Project: NÃO ALTERADO")

        print("\nMilestones validados:")

        for key in VALID_MILESTONES:
            item = milestones[key]
            print(
                f"  {key} -> #{item['number']} "
                f"{item['title']}"
            )

        results: list[dict[str, Any]] = []
        errors = 0

        for entry in selected:
            number = entry["source_issue"]

            result: dict[str, Any] = {
                "source_issue": number,
                "action": entry["action"],
                "milestone": entry["milestone"],
                "success": False,
                "issue_changed": False,
                "children": [],
                "error": None,
            }

            try:
                current = repo_issues.get(number)

                if current is None:
                    raise MigrationError(
                        f"Issue original não encontrada: #{number}"
                    )

                payload, reasons = issue_update_plan(
                    current,
                    entry,
                )

                print(
                    f"\n#{number} "
                    f"{entry['action'].upper()} "
                    f"-> {entry['milestone']}"
                )

                if entry["action"] != "keep":
                    print(entry["new_title"])

                if payload:
                    print(
                        "Issue atualizar: "
                        + ", ".join(reasons)
                    )

                    if apply:
                        updated = patch_issue(
                            number,
                            payload,
                            delay=args.delay,
                        )

                        repo_issues[number] = updated

                    result["issue_changed"] = True
                else:
                    print("Issue: SKIP")

                if entry["action"] == "split":
                    for child_index, child in enumerate(
                        entry.get("children", []),
                        start=1,
                    ):
                        child_result = create_or_reuse_child(
                            parent_entry=entry,
                            child_definition=child,
                            child_index=child_index,
                            repo_issues=repo_issues,
                            state=state,
                            apply=apply,
                            delay=args.delay,
                        )

                        result["children"].append(
                            child_result
                        )

                result["success"] = True

            except Exception as exc:
                errors += 1
                result["error"] = str(exc)

                print(
                    f"\nERRO em #{number}: {exc}"
                )

                results.append(result)

                save_result(
                    mode=(
                        "apply"
                        if apply
                        else "dry-run"
                    ),
                    results=results,
                    errors=errors,
                )

                if not args.continue_on_error:
                    print(
                        "\nMigração interrompida. "
                        "Corrija o erro e execute novamente. "
                        "A operação é idempotente."
                    )

                    return 2

                continue

            results.append(result)

            save_result(
                mode=(
                    "apply"
                    if apply
                    else "dry-run"
                ),
                results=results,
                errors=errors,
            )

        final_validation_errors: list[str] = []

        if (
            apply
            and not args.skip_final_validation
        ):
            print(
                "\nExecutando validação final via REST..."
            )

            final_validation_errors = (
                validate_final_state(selected)
            )

            if final_validation_errors:
                print(
                    "\nVALIDAÇÃO FINAL: ERROS"
                )

                for error in final_validation_errors:
                    print(
                        " -",
                        error,
                    )

                errors += len(
                    final_validation_errors
                )

            else:
                print(
                    "VALIDAÇÃO FINAL: OK"
                )

        # Sobrescreve resultado final incluindo auditoria.
        save_json(
            RESULT_FILE,
            {
                "mode": (
                    "apply"
                    if apply
                    else "dry-run"
                ),
                "repo": REPO,
                "processed": len(results),
                "errors": errors,
                "final_validation_errors": (
                    final_validation_errors
                ),
                "results": results,
            },
        )

        print("\n" + "=" * 78)

        if apply:
            print(
                "MIGRAÇÃO REST CONCLUÍDA"
            )
        else:
            print(
                "DRY-RUN REST CONCLUÍDO - "
                "nenhuma alteração realizada"
            )

        print(
            f"Processados: {len(results)}"
        )

        print(
            f"Erros: {errors}"
        )

        print(
            f"Relatório: {RESULT_FILE}"
        )

        if apply:
            print(
                f"Estado das children: {STATE_FILE}"
            )

        print("=" * 78)

        return 0 if errors == 0 else 2

    except Exception as exc:
        print(
            f"ERRO FATAL: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
