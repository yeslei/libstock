#!/usr/bin/env python3
"""
LibStock - sincronização do GitHub Project #5.

Responsabilidade
----------------
Este script NÃO altera:
- title/body das Issues
- milestones
- labels
- assignees
- estado open/closed
- parent/sub-issue

Ele sincroniza apenas o GitHub Project:
- Priority das 61 Issues originais
- Size das 61 Issues originais
- preserva Status das Issues originais
- adiciona as 4 children criadas pelos SPLITs ao Project, se necessário
- define Priority/Size das children
- define Status=Backlog somente para children novas

Entradas esperadas
------------------
backlog-migration/
├── sync_project.py
├── input/
│   ├── project-items.json
│   └── project-fields.json
├── analysis/
│   ├── migration-map.json
│   ├── issues-rest-migration-state.json
│   ├── project-sync-state.json
│   └── project-sync-result.json
└── ...

Uso
---
python sync_project.py --dry-run
python sync_project.py --apply

Filtros:
python sync_project.py --milestone V1 --dry-run
python sync_project.py --issue 16 --apply

Observação
----------
GitHub Projects v2 usa GraphQL. O script:
- consulta o Project uma única vez para obter o estado atual;
- evita mutations quando o valor já está correto;
- preserva o Status das Issues originais;
- cria checkpoints/resultados para retomada segura.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional


BASE_DIR = Path(__file__).resolve().parent

REPO = "yeslei/libstock"
OWNER = "yeslei"
PROJECT_NUMBER = 5
PROJECT_ID = "PVT_kwHOBmWjx84BiJ1B"

MAP_FILE = BASE_DIR / "analysis" / "migration-map.json"
CHILDREN_STATE_FILE = BASE_DIR / "analysis" / "issues-rest-migration-state.json"
SYNC_STATE_FILE = BASE_DIR / "analysis" / "project-sync-state.json"
RESULT_FILE = BASE_DIR / "analysis" / "project-sync-result.json"
PROJECT_FIELDS_FILE = BASE_DIR / "input" / "project-fields.json"

VALID_MILESTONES = ("V1", "V2", "V3")
DEFAULT_DELAY = 1.0
DEFAULT_MIN_GRAPHQL_REMAINING = 150

FALLBACK_FIELDS = {
    "Priority": {
        "id": "PVTSSF_lAHOBmWjx84BiJ1BzhhC4pA",
        "options": {
            "P0": "79628723",
            "P1": "0a877460",
            "P2": "da944a9c",
        },
    },
    "Size": {
        "id": "PVTSSF_lAHOBmWjx84BiJ1BzhhC4pU",
        "options": {
            "XS": "6c6483d2",
            "S": "f784b110",
            "M": "7515a9f1",
            "L": "817d0097",
            "XL": "db339eb2",
        },
    },
    "Status": {
        "id": "PVTSSF_lAHOBmWjx84BiJ1BzhhC4e8",
        "options": {
            "Backlog": "f75ad846",
            "Priorizado": "61e4505c",
            "In progress": "47fc9ee4",
            "In review": "df73e18b",
            "Done": "98236657",
        },
    },
}


class SyncError(RuntimeError):
    pass


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise SyncError(f"Arquivo não encontrado: {path}")

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
        raise SyncError(f"JSON inválido em {path}: {exc}") from exc


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run(cmd: list[str], *, input_text: Optional[str] = None) -> str:
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

        raise SyncError(
            "Falha: "
            + " ".join(cmd)
            + (f"\nstdout:\n{stdout}" if stdout else "")
            + (f"\nstderr:\n{stderr}" if stderr else "")
        )

    return (proc.stdout or "").strip()


def run_json(cmd: list[str], *, input_data: Any = None) -> Any:
    input_text = None
    if input_data is not None:
        input_text = json.dumps(input_data, ensure_ascii=False)

    text = run(cmd, input_text=input_text)

    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SyncError(
            "Comando não retornou JSON válido:\n"
            + " ".join(cmd)
            + f"\nResposta:\n{text}"
        ) from exc


def check_auth() -> None:
    run(["gh", "auth", "status"])


def sleep_after_mutation(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)


def graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    cmd = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={query}",
    ]

    for key, value in variables.items():
        if value is None:
            continue

        flag = "-F" if isinstance(value, (int, float, bool)) else "-f"
        rendered = str(value).lower() if isinstance(value, bool) else str(value)

        cmd += [
            flag,
            f"{key}={rendered}",
        ]

    data = run_json(cmd)

    if not isinstance(data, dict):
        raise SyncError("Resposta GraphQL inválida.")

    if data.get("errors"):
        raise SyncError(
            "GraphQL retornou erros:\n"
            + json.dumps(
                data["errors"],
                ensure_ascii=False,
                indent=2,
            )
        )

    return data.get("data") or {}


RATE_LIMIT_QUERY = """
query {
  rateLimit {
    limit
    used
    remaining
    resetAt
  }
}
"""


def ensure_rate_limit(min_remaining: int) -> None:
    data = graphql(RATE_LIMIT_QUERY, {})
    info = data.get("rateLimit") or {}

    print(
        f"GraphQL: used={info.get('used')} "
        f"remaining={info.get('remaining')} "
        f"resetAt={info.get('resetAt')}"
    )

    remaining = info.get("remaining")

    if remaining is not None and int(remaining) < min_remaining:
        raise SyncError(
            f"GraphQL remaining={remaining}, abaixo do mínimo "
            f"{min_remaining}. Aguarde o reset."
        )


def load_project_fields() -> dict[str, dict[str, Any]]:
    if not PROJECT_FIELDS_FILE.exists():
        return FALLBACK_FIELDS

    try:
        data = load_json(PROJECT_FIELDS_FILE)

        raw_fields = (
            data.get("fields", [])
            if isinstance(data, dict)
            else data
        )

        result: dict[str, dict[str, Any]] = {}

        for field in raw_fields or []:
            name = field.get("name")
            field_id = field.get("id")

            if name not in {"Priority", "Size", "Status"} or not field_id:
                continue

            options = {}

            for option in field.get("options") or []:
                if option.get("name") and option.get("id"):
                    options[str(option["name"])] = str(option["id"])

            result[name] = {
                "id": str(field_id),
                "options": options,
            }

        if all(
            key in result
            for key in ("Priority", "Size", "Status")
        ):
            return result

    except Exception:
        pass

    return FALLBACK_FIELDS


PROJECT_ITEMS_QUERY = """
query(
  $projectId: ID!,
  $after: String
) {
  node(id: $projectId) {
    ... on ProjectV2 {
      id
      items(first: 100, after: $after) {
        nodes {
          id
          content {
            ... on Issue {
              id
              number
              url
              title
            }
          }
          fieldValues(first: 30) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                optionId
                field {
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                  }
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


def load_current_project_items() -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    after: Optional[str] = None

    while True:
        data = graphql(
            PROJECT_ITEMS_QUERY,
            {
                "projectId": PROJECT_ID,
                "after": after,
            },
        )

        node = data.get("node") or {}
        items = node.get("items") or {}

        for project_item in items.get("nodes") or []:
            content = project_item.get("content") or {}
            number = content.get("number")

            if number is None:
                continue

            fields: dict[str, str] = {}

            values = (
                (project_item.get("fieldValues") or {})
                .get("nodes")
                or []
            )

            for value in values:
                field = value.get("field") or {}
                field_name = field.get("name")
                field_value = value.get("name")

                if field_name and field_value:
                    fields[str(field_name)] = str(field_value)

            result[int(number)] = {
                "item_id": project_item.get("id"),
                "content_node_id": content.get("id"),
                "url": content.get("url"),
                "title": content.get("title"),
                "fields": fields,
            }

        page_info = items.get("pageInfo") or {}

        if not page_info.get("hasNextPage"):
            break

        after = page_info.get("endCursor")

    return result


def get_issue_via_rest(number: int) -> dict[str, Any]:
    data = run_json([
        "gh",
        "api",
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
        f"repos/{REPO}/issues/{number}",
    ])

    if not isinstance(data, dict):
        raise SyncError(
            f"Não foi possível carregar Issue #{number} via REST."
        )

    return data


ADD_ITEM_MUTATION = """
mutation(
  $projectId: ID!,
  $contentId: ID!
) {
  addProjectV2ItemById(
    input: {
      projectId: $projectId
      contentId: $contentId
    }
  ) {
    item {
      id
    }
  }
}
"""


def add_issue_to_project(
    *,
    issue_number: int,
    issue_node_id: str,
    delay: float,
) -> str:
    data = graphql(
        ADD_ITEM_MUTATION,
        {
            "projectId": PROJECT_ID,
            "contentId": issue_node_id,
        },
    )

    item = (
        data.get("addProjectV2ItemById") or {}
    ).get("item") or {}

    item_id = item.get("id")

    if not item_id:
        raise SyncError(
            f"Não foi possível obter Project item ID da Issue #{issue_number}."
        )

    sleep_after_mutation(delay)

    return str(item_id)


SET_SINGLE_SELECT_MUTATION = """
mutation(
  $projectId: ID!,
  $itemId: ID!,
  $fieldId: ID!,
  $optionId: String!
) {
  updateProjectV2ItemFieldValue(
    input: {
      projectId: $projectId
      itemId: $itemId
      fieldId: $fieldId
      value: {
        singleSelectOptionId: $optionId
      }
    }
  ) {
    projectV2Item {
      id
    }
  }
}
"""


def set_single_select_field(
    *,
    item_id: str,
    field_name: str,
    desired_value: str,
    fields_config: dict[str, dict[str, Any]],
    delay: float,
) -> None:
    field = fields_config.get(field_name)

    if not field:
        raise SyncError(
            f"Configuração do campo `{field_name}` não encontrada."
        )

    option_id = (
        field.get("options") or {}
    ).get(desired_value)

    if not option_id:
        raise SyncError(
            f"Opção `{desired_value}` não encontrada em `{field_name}`."
        )

    graphql(
        SET_SINGLE_SELECT_MUTATION,
        {
            "projectId": PROJECT_ID,
            "itemId": item_id,
            "fieldId": field["id"],
            "optionId": option_id,
        },
    )

    sleep_after_mutation(delay)


def validate_map(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise SyncError(
            "analysis/migration-map.json deve conter uma lista."
        )

    seen = set()

    for entry in data:
        number = entry.get("source_issue")
        milestone = entry.get("milestone")

        if not isinstance(number, int):
            raise SyncError(
                f"source_issue inválido: {number!r}"
            )

        if number in seen:
            raise SyncError(
                f"Issue duplicada no migration-map: #{number}"
            )

        seen.add(number)

        if milestone not in VALID_MILESTONES:
            raise SyncError(
                f"Milestone inválido em #{number}: {milestone}"
            )

    return data


def load_children() -> list[dict[str, Any]]:
    state = load_json(
        CHILDREN_STATE_FILE,
        default={"children": {}},
    )

    raw = state.get("children") or {}
    result = []

    for key, child in raw.items():
        if child.get("number") is None:
            continue

        data = dict(child)
        data["state_key"] = key
        result.append(data)

    return result


def parent_entry_for_child(
    child: dict[str, Any],
    entries_by_number: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    parent_number = int(child["parent"])
    parent = entries_by_number.get(parent_number)

    if not parent:
        raise SyncError(
            f"Parent #{parent_number} da child #{child['number']} "
            "não existe no migration-map."
        )

    return parent


def sync_existing_issue(
    *,
    entry: dict[str, Any],
    project_items: dict[int, dict[str, Any]],
    fields_config: dict[str, dict[str, Any]],
    apply: bool,
    delay: float,
) -> dict[str, Any]:
    number = entry["source_issue"]
    item = project_items.get(number)

    if not item:
        raise SyncError(
            f"Issue original #{number} não está no GitHub Project."
        )

    item_id = item.get("item_id")

    if not item_id:
        raise SyncError(
            f"Project item ID ausente para #{number}."
        )

    current_fields = item.get("fields") or {}
    changes = []

    for field_name, desired in (
        ("Priority", entry.get("priority")),
        ("Size", entry.get("size")),
    ):
        if not desired:
            continue

        current = current_fields.get(field_name)

        if current == desired:
            print(f"  {field_name}={desired}: SKIP")
            continue

        print(
            f"  {field_name}: "
            f"{current or '<vazio>'} -> {desired}"
        )

        changes.append(
            {
                "field": field_name,
                "from": current,
                "to": desired,
            }
        )

        if apply:
            set_single_select_field(
                item_id=item_id,
                field_name=field_name,
                desired_value=desired,
                fields_config=fields_config,
                delay=delay,
            )

            current_fields[field_name] = desired

    print(
        f"  Status={current_fields.get('Status') or '<vazio>'}: PRESERVADO"
    )

    return {
        "number": number,
        "kind": "original",
        "changes": changes,
        "status_preserved": True,
    }


def sync_child(
    *,
    child: dict[str, Any],
    parent_entry: dict[str, Any],
    project_items: dict[int, dict[str, Any]],
    fields_config: dict[str, dict[str, Any]],
    apply: bool,
    delay: float,
) -> dict[str, Any]:
    number = int(child["number"])
    item = project_items.get(number)
    added = False

    if not item:
        print("  Project: adicionar child")

        if not apply:
            item = {
                "item_id": None,
                "fields": {},
            }
        else:
            issue = get_issue_via_rest(number)
            issue_node_id = issue.get("node_id")

            if not issue_node_id:
                raise SyncError(
                    f"node_id ausente na Issue child #{number}."
                )

            item_id = add_issue_to_project(
                issue_number=number,
                issue_node_id=str(issue_node_id),
                delay=delay,
            )

            item = {
                "item_id": item_id,
                "content_node_id": issue_node_id,
                "url": issue.get("html_url"),
                "title": issue.get("title"),
                "fields": {},
            }

            project_items[number] = item
            added = True

    else:
        print("  Project: SKIP (child já está no Project)")

    desired = {
        "Priority": (
            child.get("priority")
            or parent_entry.get("priority")
        ),
        "Size": (
            child.get("size")
            or parent_entry.get("size")
        ),
        "Status": "Backlog",
    }

    changes = []
    current_fields = item.get("fields") or {}
    item_id = item.get("item_id")

    for field_name, target in desired.items():
        if not target:
            continue

        current = current_fields.get(field_name)

        if current == target:
            print(f"  {field_name}={target}: SKIP")
            continue

        print(
            f"  {field_name}: "
            f"{current or '<vazio>'} -> {target}"
        )

        changes.append(
            {
                "field": field_name,
                "from": current,
                "to": target,
            }
        )

        if apply:
            if not item_id:
                raise SyncError(
                    f"Project item ID ausente para child #{number}."
                )

            set_single_select_field(
                item_id=str(item_id),
                field_name=field_name,
                desired_value=str(target),
                fields_config=fields_config,
                delay=delay,
            )

            current_fields[field_name] = str(target)

    return {
        "number": number,
        "kind": "child",
        "parent": int(child["parent"]),
        "added_to_project": added,
        "changes": changes,
    }


def save_result(
    *,
    mode: str,
    results: list[dict[str, Any]],
    errors: int,
    total_project_items_seen: int,
) -> None:
    save_json(
        RESULT_FILE,
        {
            "mode": mode,
            "repo": REPO,
            "project": f"{OWNER}#{PROJECT_NUMBER}",
            "processed": len(results),
            "errors": errors,
            "project_items_seen": total_project_items_seen,
            "results": results,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sincroniza Priority/Size/Status e children "
            "no GitHub Project do LibStock."
        )
    )

    mode = parser.add_mutually_exclusive_group(required=True)

    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que mudaria sem alterar o Project.",
    )

    mode.add_argument(
        "--apply",
        action="store_true",
        help="Aplica alterações no Project.",
    )

    parser.add_argument(
        "--milestone",
        choices=["V1", "V2", "V3", "all"],
        default="all",
    )

    parser.add_argument(
        "--issue",
        type=int,
        help="Sincroniza apenas uma Issue original.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=(
            "Segundos entre mutations GraphQL. "
            f"Padrão: {DEFAULT_DELAY}."
        ),
    )

    parser.add_argument(
        "--min-graphql-remaining",
        type=int,
        default=DEFAULT_MIN_GRAPHQL_REMAINING,
        help=(
            "Não inicia APPLY se remaining estiver abaixo deste valor. "
            f"Padrão: {DEFAULT_MIN_GRAPHQL_REMAINING}."
        ),
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
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

        migration_map = validate_map(
            load_json(MAP_FILE)
        )

        entries_by_number = {
            entry["source_issue"]: entry
            for entry in migration_map
        }

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
            print("Nenhuma Issue original selecionada.")
            return 1

        children = load_children()

        selected_numbers = {
            entry["source_issue"]
            for entry in selected
        }

        selected_children = [
            child
            for child in children
            if int(child["parent"]) in selected_numbers
        ]

        fields_config = load_project_fields()

        print("=" * 78)
        print("LIBSTOCK - SYNC DO GITHUB PROJECT")
        print("=" * 78)

        print(
            f"Modo={'APPLY' if apply else 'DRY-RUN'} "
            f"| originais={len(selected)} "
            f"| children={len(selected_children)}"
        )

        print("Issues/body/milestone: NÃO ALTERADOS")
        print("Status das Issues originais: PRESERVADO")

        ensure_rate_limit(
            args.min_graphql_remaining
        )

        print("\nCarregando estado atual do Project...")
        project_items = load_current_project_items()

        print(
            f"Project items encontrados: {len(project_items)}"
        )

        results: list[dict[str, Any]] = []
        errors = 0

        for entry in selected:
            number = entry["source_issue"]

            print(
                f"\n#{number} ORIGINAL "
                f"-> {entry['milestone']}"
            )

            try:
                result = sync_existing_issue(
                    entry=entry,
                    project_items=project_items,
                    fields_config=fields_config,
                    apply=apply,
                    delay=args.delay,
                )

                results.append(result)

            except Exception as exc:
                errors += 1

                print(f"ERRO em #{number}: {exc}")

                results.append(
                    {
                        "number": number,
                        "kind": "original",
                        "error": str(exc),
                    }
                )

                save_result(
                    mode="apply" if apply else "dry-run",
                    results=results,
                    errors=errors,
                    total_project_items_seen=len(project_items),
                )

                if not args.continue_on_error:
                    return 2

        for child in selected_children:
            number = int(child["number"])
            parent = int(child["parent"])

            print(
                f"\n#{number} CHILD "
                f"(parent #{parent})"
            )

            try:
                parent_entry = parent_entry_for_child(
                    child,
                    entries_by_number,
                )

                result = sync_child(
                    child=child,
                    parent_entry=parent_entry,
                    project_items=project_items,
                    fields_config=fields_config,
                    apply=apply,
                    delay=args.delay,
                )

                results.append(result)

            except Exception as exc:
                errors += 1

                print(
                    f"ERRO em child #{number}: {exc}"
                )

                results.append(
                    {
                        "number": number,
                        "kind": "child",
                        "parent": parent,
                        "error": str(exc),
                    }
                )

                save_result(
                    mode="apply" if apply else "dry-run",
                    results=results,
                    errors=errors,
                    total_project_items_seen=len(project_items),
                )

                if not args.continue_on_error:
                    return 2

        if apply:
            ensure_rate_limit(
                args.min_graphql_remaining
            )

        save_result(
            mode="apply" if apply else "dry-run",
            results=results,
            errors=errors,
            total_project_items_seen=len(project_items),
        )

        print("\n" + "=" * 78)

        if apply:
            print("PROJECT SYNC CONCLUÍDO")
        else:
            print(
                "DRY-RUN DO PROJECT CONCLUÍDO - "
                "nenhuma alteração realizada"
            )

        print(
            f"Originais processadas: {len(selected)}"
        )

        print(
            f"Children processadas: {len(selected_children)}"
        )

        print(
            f"Erros: {errors}"
        )

        print(
            f"Relatório: {RESULT_FILE}"
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
