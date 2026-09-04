#!/usr/bin/env python3
"""
LibStock - migração idempotente do backlog.

Esta versão EVITA consultas GraphQL de descoberta no início.
Ela usa os IDs já conhecidos/exportados do GitHub Project e só faz mutations
quando necessário.

Estrutura esperada:
backlog-migration/
├── migrate_backlog.py
├── input/
│   ├── project-items.json
│   └── project-fields.json   # opcional nesta versão
├── analysis/
│   ├── migration-map.json
│   ├── migration-state.json
│   └── migration-result.json
└── stories/
    ├── V1/
    ├── V2/
    └── V3/

Uso:
    python migrate_backlog.py --dry-run
    python migrate_backlog.py --apply

Filtros:
    python migrate_backlog.py --issue 20 --dry-run
    python migrate_backlog.py --milestone V1 --apply

Observações:
- KEEP preserva título/body.
- REWRITE atualiza título/body/milestone.
- SPLIT transforma a original em EPIC e cria/reutiliza children.
- Status de cards existentes é preservado.
- Novas sub-issues recebem Status=Backlog.
- project-items.json é usado como cache local para evitar `gh project item-list`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


BASE_DIR = Path(__file__).resolve().parent

REPO = "yeslei/libstock"
PROJECT_OWNER = "yeslei"
PROJECT_NUMBER = 5

# Project node ID já conhecido.
PROJECT_ID = "PVT_kwHOBmWjx84BiJ1B"

MAP_FILE = BASE_DIR / "analysis" / "migration-map.json"
STATE_FILE = BASE_DIR / "analysis" / "migration-state.json"
RESULT_FILE = BASE_DIR / "analysis" / "migration-result.json"
PROJECT_ITEMS_FILE = BASE_DIR / "input" / "project-items.json"
STORIES_DIR = BASE_DIR / "stories"

VALID_MILESTONES = ("V1", "V2", "V3")

# IDs exportados anteriormente do Project.
PROJECT_FIELDS = {
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


def run(cmd: list[str]) -> str:
    proc = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.returncode != 0:
        raise MigrationError(
            "Falha: " + " ".join(cmd)
            + (f"\nstdout:\n{proc.stdout.strip()}" if proc.stdout.strip() else "")
            + (f"\nstderr:\n{proc.stderr.strip()}" if proc.stderr.strip() else "")
        )

    return proc.stdout.strip()


def run_json(cmd: list[str]) -> Any:
    text = run(cmd)
    return json.loads(text) if text else None


def issue_url(number: int) -> str:
    return f"https://github.com/{REPO}/issues/{number}"


def check_auth() -> None:
    run(["gh", "auth", "status"])


def resolve_milestones() -> dict[str, str]:
    # REST, não depende de GraphQL.
    data = run_json([
        "gh",
        "api",
        f"repos/{REPO}/milestones",
        "--paginate",
    ])

    result: dict[str, str] = {}

    for item in data or []:
        title = str(item.get("title", ""))

        for key in VALID_MILESTONES:
            if (
                title == key
                or title.startswith(f"{key} -")
                or title.startswith(f"{key} –")
            ):
                result[key] = title

    missing = [key for key in VALID_MILESTONES if key not in result]
    if missing:
        raise MigrationError(
            "Milestones não encontrados: " + ", ".join(missing)
        )

    return result


def load_repo_issues() -> dict[int, dict[str, Any]]:
    # REST/Issue listing; uma consulta para toda execução.
    data = run_json([
        "gh",
        "issue",
        "list",
        "--repo",
        REPO,
        "--state",
        "all",
        "--limit",
        "300",
        "--json",
        "number,title,body,milestone,url,state",
    ])

    return {
        int(item["number"]): item
        for item in data or []
        if item.get("number") is not None
    }


def load_project_items_cache() -> dict[int, dict[str, Any]]:
    data = load_json(PROJECT_ITEMS_FILE)

    items = data.get("items", data) if isinstance(data, dict) else data

    result: dict[int, dict[str, Any]] = {}

    for item in items or []:
        content = item.get("content") or {}
        number = content.get("number")

        try:
            number = int(number)
        except (TypeError, ValueError):
            continue

        result[number] = item

    return result


def get_cached_project_value(
    item: dict[str, Any],
    field_name: str,
) -> Optional[str]:
    candidates = [
        field_name,
        field_name.lower(),
        field_name.replace(" ", "_").lower(),
    ]

    for key in candidates:
        value = item.get(key)

        if value in (None, ""):
            continue

        if isinstance(value, dict):
            return (
                value.get("name")
                or value.get("title")
                or value.get("value")
            )

        return str(value)

    return None


def graphql_remaining() -> Optional[int]:
    # REST endpoint de rate limit.
    try:
        data = run_json(["gh", "api", "rate_limit"])
        return int(data["resources"]["graphql"]["remaining"])
    except Exception:
        return None


def find_story_file(
    issue_number: int,
    milestone: str,
    kind: str,
    child_index: Optional[int] = None,
) -> Path:
    folder = STORIES_DIR / milestone

    if kind == "normal":
        files = [
            p
            for p in folder.glob(f"issue-{issue_number}-*.md")
            if "-child-" not in p.name
            and "epic" not in p.name.lower()
        ]

    elif kind == "epic":
        files = list(folder.glob(f"issue-{issue_number}-*epic*.md"))

    elif kind == "child":
        files = list(
            folder.glob(
                f"issue-{issue_number}-child-{child_index}-*.md"
            )
        )

    else:
        raise MigrationError(f"Tipo de story inválido: {kind}")

    files = sorted(set(files))

    if len(files) != 1:
        raise MigrationError(
            f"Esperado 1 arquivo para #{issue_number} ({kind}); "
            f"encontrados {len(files)}: {files}"
        )

    return files[0]


def validate_map(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise MigrationError("migration-map.json deve conter uma lista.")

    for entry in data:
        action = str(entry.get("action", "")).lower()
        milestone = entry.get("milestone")

        if action not in {"keep", "rewrite", "split"}:
            raise MigrationError(
                f"Ação inválida em #{entry.get('source_issue')}: {action}"
            )

        if milestone not in VALID_MILESTONES:
            raise MigrationError(
                f"Milestone inválido em #{entry.get('source_issue')}: "
                f"{milestone}"
            )

        entry["action"] = action

    return data


def desired_body_file(entry: dict[str, Any]) -> Optional[Path]:
    number = entry["source_issue"]

    if entry["action"] == "rewrite":
        return find_story_file(
            number,
            entry["milestone"],
            "normal",
        )

    if entry["action"] == "split":
        return find_story_file(
            number,
            entry["milestone"],
            "epic",
        )

    return None


def issue_needs_update(
    current: dict[str, Any],
    entry: dict[str, Any],
    milestone_title: str,
    body_file: Optional[Path],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    current_milestone = (current.get("milestone") or {}).get("title")

    if current_milestone != milestone_title:
        reasons.append("milestone")

    if entry["action"] != "keep":
        if current.get("title") != entry["new_title"]:
            reasons.append("title")

        desired_body = body_file.read_text(encoding="utf-8")
        current_body = current.get("body") or ""

        if (
            current_body.replace("\r\n", "\n").strip()
            != desired_body.replace("\r\n", "\n").strip()
        ):
            reasons.append("body")

    return bool(reasons), reasons


def update_issue(
    entry: dict[str, Any],
    current: dict[str, Any],
    milestone_title: str,
    apply: bool,
) -> bool:
    number = entry["source_issue"]
    body_file = desired_body_file(entry)

    needs_update, reasons = issue_needs_update(
        current,
        entry,
        milestone_title,
        body_file,
    )

    print(
        f"\n#{number} {entry['action'].upper()} -> {entry['milestone']}"
    )

    if entry["action"] != "keep":
        print(entry["new_title"])

    if not needs_update:
        print("Issue: SKIP")
        return False

    print("Issue:", ", ".join(reasons))

    if not apply:
        return True

    cmd = [
        "gh",
        "issue",
        "edit",
        str(number),
        "--repo",
        REPO,
        "--milestone",
        milestone_title,
    ]

    if entry["action"] != "keep":
        cmd += [
            "--title",
            entry["new_title"],
            "--body-file",
            str(body_file),
        ]

    run(cmd)

    current["milestone"] = {"title": milestone_title}

    if entry["action"] != "keep":
        current["title"] = entry["new_title"]
        current["body"] = body_file.read_text(encoding="utf-8")

    return True


def set_project_field(
    item: dict[str, Any],
    field_name: str,
    desired_value: Optional[str],
    apply: bool,
) -> bool:
    if not desired_value:
        return False

    config = PROJECT_FIELDS[field_name]

    option_id = config["options"].get(str(desired_value))
    if not option_id:
        raise MigrationError(
            f"Valor inválido para {field_name}: {desired_value}"
        )

    item_id = item.get("id")
    if not item_id:
        raise MigrationError(
            f"Project item sem ID para {field_name}={desired_value}"
        )

    current = get_cached_project_value(item, field_name)

    if current == str(desired_value):
        print(f"Project {field_name}={desired_value}: SKIP")
        return False

    print(
        f"Project {field_name}={desired_value}"
        + (f" (cache={current})" if current else "")
    )

    if apply:
        run([
            "gh",
            "project",
            "item-edit",
            "--id",
            str(item_id),
            "--project-id",
            PROJECT_ID,
            "--field-id",
            config["id"],
            "--single-select-option-id",
            option_id,
        ])

        item[field_name.lower()] = str(desired_value)

    return True


def exact_issue_by_title(
    repo_issues: dict[int, dict[str, Any]],
    title: str,
) -> Optional[dict[str, Any]]:
    matches = [
        issue
        for issue in repo_issues.values()
        if str(issue.get("title", "")).strip() == title.strip()
    ]

    if len(matches) > 1:
        raise MigrationError(
            f"Mais de uma Issue possui o título `{title}`."
        )

    return matches[0] if matches else None


def add_child_to_project(
    child_number: int,
    child_url: str,
    project_items: dict[int, dict[str, Any]],
    apply: bool,
) -> Optional[dict[str, Any]]:
    if child_number in project_items:
        print("  Project child: SKIP")
        return project_items[child_number]

    print(f"  Project child: adicionar #{child_number}")

    if not apply:
        return None

    data = run_json([
        "gh",
        "project",
        "item-add",
        str(PROJECT_NUMBER),
        "--owner",
        PROJECT_OWNER,
        "--url",
        child_url,
        "--format",
        "json",
    ])

    if not isinstance(data, dict) or not data.get("id"):
        raise MigrationError(
            f"Não foi possível obter item ID da child #{child_number}."
        )

    data.setdefault("content", {})
    if isinstance(data["content"], dict):
        data["content"]["number"] = child_number

    project_items[child_number] = data

    return data


def create_or_reuse_child(
    parent_entry: dict[str, Any],
    child: dict[str, Any],
    child_index: int,
    milestone_title: str,
    state: dict[str, Any],
    repo_issues: dict[int, dict[str, Any]],
    project_items: dict[int, dict[str, Any]],
    apply: bool,
    skip_project: bool,
) -> dict[str, Any]:
    parent_number = parent_entry["source_issue"]
    state_key = f"{parent_number}:{child_index}"
    title = child["title"]

    children_state = state.setdefault("children", {})

    current = None

    saved = children_state.get(state_key)
    if saved:
        saved_number = saved.get("number")
        if saved_number in repo_issues:
            current = repo_issues[saved_number]

    if current is None:
        current = exact_issue_by_title(repo_issues, title)

    body_file = find_story_file(
        parent_number,
        parent_entry["milestone"],
        "child",
        child_index,
    )

    if current is None:
        print(f"  child {child_index}: CREATE {title}")

        if not apply:
            return {
                "title": title,
                "number": None,
                "created": True,
            }

        url = run([
            "gh",
            "issue",
            "create",
            "--repo",
            REPO,
            "--title",
            title,
            "--body-file",
            str(body_file),
            "--milestone",
            milestone_title,
            "--parent",
            str(parent_number),
        ])

        number = int(url.rstrip("/").split("/")[-1])

        current = {
            "number": number,
            "title": title,
            "url": url,
            "body": body_file.read_text(encoding="utf-8"),
            "milestone": {"title": milestone_title},
        }

        repo_issues[number] = current

    else:
        number = int(current["number"])
        url = current.get("url") or issue_url(number)

        print(f"  child {child_index}: REUSE #{number}")

        if apply and state_key not in children_state:
            # Garante vínculo parent para child antiga encontrada por título.
            run([
                "gh",
                "issue",
                "edit",
                str(number),
                "--repo",
                REPO,
                "--parent",
                str(parent_number),
            ])

    if apply:
        children_state[state_key] = {
            "number": int(current["number"]),
            "url": current.get("url") or issue_url(int(current["number"])),
            "title": title,
            "parent": parent_number,
        }
        save_json(STATE_FILE, state)

    if not skip_project and apply:
        child_number = int(current["number"])
        child_url = current.get("url") or issue_url(child_number)

        item = add_child_to_project(
            child_number,
            child_url,
            project_items,
            apply=True,
        )

        if item:
            set_project_field(
                item,
                "Priority",
                child.get("priority") or parent_entry.get("priority"),
                True,
            )

            set_project_field(
                item,
                "Size",
                child.get("size") or parent_entry.get("size"),
                True,
            )

            set_project_field(
                item,
                "Status",
                "Backlog",
                True,
            )

    elif not skip_project and not apply:
        print(
            "  child Project: "
            f"Priority={child.get('priority') or parent_entry.get('priority')}, "
            f"Size={child.get('size') or parent_entry.get('size')}, "
            "Status=Backlog"
        )

    return {
        "title": title,
        "number": current.get("number") if current else None,
        "created": current is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")

    parser.add_argument(
        "--milestone",
        choices=["V1", "V2", "V3", "all"],
        default="all",
    )

    parser.add_argument("--issue", type=int)

    parser.add_argument(
        "--skip-project",
        action="store_true",
        help="Não altera campos do Project.",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
    )

    args = parser.parse_args()
    apply = args.apply

    try:
        check_auth()

        migration_map = validate_map(load_json(MAP_FILE))
        state = load_json(STATE_FILE, default={"children": {}})

        milestones = resolve_milestones()
        repo_issues = load_repo_issues()

        project_items: dict[int, dict[str, Any]] = {}
        if not args.skip_project:
            project_items = load_project_items_cache()

        selected = [
            entry
            for entry in migration_map
            if (
                (args.milestone == "all" or entry["milestone"] == args.milestone)
                and (
                    args.issue is None
                    or entry["source_issue"] == args.issue
                )
            )
        ]

        if not selected:
            print("Nenhuma Issue selecionada.")
            return 1

        print("=" * 72)
        print("LIBSTOCK - MIGRAÇÃO DO BACKLOG")
        print("=" * 72)
        print(
            f"Modo={'APPLY' if apply else 'DRY-RUN'} | "
            f"cards={len(selected)}"
        )
        print(
            "Project discovery=OFF "
            "(usando cache local + IDs conhecidos)"
        )

        remaining = graphql_remaining()
        if remaining is not None:
            print(f"GraphQL remaining no início: {remaining}")

        results = []
        errors = 0

        for entry in selected:
            number = entry["source_issue"]

            result = {
                "source_issue": number,
                "success": False,
                "error": None,
                "children": [],
            }

            try:
                current = repo_issues.get(number)

                if not current:
                    raise MigrationError(
                        f"Issue original não encontrada: #{number}"
                    )

                milestone_title = milestones[entry["milestone"]]

                update_issue(
                    entry,
                    current,
                    milestone_title,
                    apply,
                )

                if not args.skip_project:
                    item = project_items.get(number)

                    if not item:
                        raise MigrationError(
                            f"Project item não encontrado no cache para #{number}. "
                            "Atualize input/project-items.json depois que o rate "
                            "limit permitir, ou use --skip-project."
                        )

                    set_project_field(
                        item,
                        "Priority",
                        entry.get("priority"),
                        apply,
                    )

                    set_project_field(
                        item,
                        "Size",
                        entry.get("size"),
                        apply,
                    )

                    # Status de card existente nunca é alterado.

                if entry["action"] == "split":
                    for child_index, child in enumerate(
                        entry.get("children", []),
                        start=1,
                    ):
                        child_result = create_or_reuse_child(
                            entry,
                            child,
                            child_index,
                            milestone_title,
                            state,
                            repo_issues,
                            project_items,
                            apply,
                            args.skip_project,
                        )

                        result["children"].append(child_result)

                result["success"] = True

            except Exception as exc:
                errors += 1
                result["error"] = str(exc)

                print(f"\nERRO em #{number}: {exc}")

                results.append(result)

                save_json(
                    RESULT_FILE,
                    {
                        "mode": "apply" if apply else "dry-run",
                        "processed": len(results),
                        "errors": errors,
                        "results": results,
                    },
                )

                if not args.continue_on_error:
                    print(
                        "\nInterrompido. O script pode ser executado novamente."
                    )
                    return 2

                continue

            results.append(result)

            save_json(
                RESULT_FILE,
                {
                    "mode": "apply" if apply else "dry-run",
                    "processed": len(results),
                    "errors": errors,
                    "results": results,
                },
            )

        remaining = graphql_remaining()
        if remaining is not None:
            print(f"\nGraphQL remaining no fim: {remaining}")

        print("\n" + "=" * 72)
        print(
            "MIGRAÇÃO CONCLUÍDA"
            if apply
            else "DRY-RUN CONCLUÍDO"
        )
        print(f"Processados: {len(results)}")
        print(f"Erros: {errors}")
        print(f"Relatório: {RESULT_FILE}")
        print("=" * 72)

        return 0 if errors == 0 else 2

    except Exception as exc:
        print(f"ERRO FATAL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
