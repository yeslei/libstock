import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent

ISSUES_FILE = BASE_DIR / "input" / "issues.json"
PROJECT_ITEMS_FILE = BASE_DIR / "input" / "project-items.json"
OUTPUT_FILE = BASE_DIR / "analysis" / "migration-map.json"

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


# =========================================================
# CONFIGURAÇÃO DE MILESTONES
# =========================================================

V1_RANGES = [
    range(4, 34),       # preparação + usuários + acervo + consulta + empréstimos
    range(51, 54),      # testes relacionados à V1
]

V2_RANGES = [
    range(34, 43),      # vendas + reservas
    range(54, 56),      # testes V2
]

V3_RANGES = [
    range(43, 51),      # notificações + segurança
    range(56, 64),      # testes finais + integração + entrega
]

EXPLICIT_MILESTONES = { 
    66: "V1",           # tela de home
}
MILESTONE_BY_ISSUE = {
    # Preparação
    4: "V1",
    5: "V1",
    6: "V1",
    7: "V1",
    8: "V1",

    # Usuários
    9: "V1",
    10: "V1",
    11: "V1",
    12: "V1",
    13: "V1",
    14: "V1",
    15: "V1",  # revisar

    # Acervo
    16: "V1",
    17: "V1",
    18: "V1",
    19: "V1",
    20: "V1",
    21: "V1",
    22: "V1",

    # Consulta
    23: "V1",
    24: "V1",
    25: "V1",
    26: "V1",
    27: "V1",

    # Empréstimos/devoluções
    28: "V2",
    29: "V2",
    30: "V2",
    31: "V2",
    32: "V2",
    33: "V2",

    # Vendas / reservas
    34: "V2",
    35: "V2",
    36: "V2",
    37: "V2",
    38: "V2",
    39: "V2",
    40: "V2",
    41: "V2",
    42: "V2",

    # Alertas / segurança
    43: "V3",
    44: "V3",
    45: "V3",
    46: "V3",
    47: "V3",
    48: "V3",
    49: "V3",
    50: "V3",

    # Testes
    51: "V1",
    52: "V1",
    53: "V2",
    54: "V2",
    55: "V2",
    56: "V3",
    57: "V3",
    58: "V3",

    # Integração/entrega
    59: "V3",
    60: "V3",
    61: "V3",
    62: "V3",
    63: "V3",

    # Home
    66: "V1",
}

# =========================================================
# ISSUES QUE DEVEM SER DIVIDIDAS
# =========================================================

SPLIT_ISSUES = {
    12: {
        "new_title": "[EPIC] Consultar e manter dados de usuários",
        "children": [
            "[US] Consultar usuário",
            "[US] Atualizar dados de usuário",
        ],
    },

    18: {
        "new_title": "[EPIC] Consultar e manter obras",
        "children": [
            "[US] Consultar obra",
            "[US] Atualizar obra",
        ],
    },
}
TITLE_OVERRIDES = {
    66: "[US] Visualizar acervos disponíveis na página inicial",
}
# =========================================================
# CLASSIFICAÇÃO DE TIPO
# =========================================================

TECHNICAL_ISSUES = {
    4, 5, 6, 7, 8,
    59, 60, 62,
}

QA_ISSUES = set(range(51, 59)) | {61}

DOCUMENTATION_ISSUES = {63}


# =========================================================
# FUNÇÕES
# =========================================================

def get_milestone(issue_number: int) -> str | None:
    return MILESTONE_BY_ISSUE.get(issue_number)


def get_type(issue_number: int) -> str:
    if issue_number in SPLIT_ISSUES:
        return "epic"

    if issue_number in QA_ISSUES:
        return "qa"

    if issue_number in DOCUMENTATION_ISSUES:
        return "documentation"

    if issue_number in TECHNICAL_ISSUES:
        return "technical"

    return "user-story"


def get_prefix(issue_type: str) -> str:
    return {
        "user-story": "[US]",
        "technical": "[TECH]",
        "qa": "[QA]",
        "documentation": "[DOC]",
        "epic": "[EPIC]",
    }[issue_type]


def clean_title(title: str) -> str:
    """
    Remove 'Implementar' quando o título será transformado
    em história de usuário.
    """
    title = title.strip()

    title = re.sub(
        r"^Implementar\s+",
        "",
        title,
        flags=re.IGNORECASE,
    )

    return title


def generate_new_title(
    issue_number: int,
    title: str,
    issue_type: str,
) -> str:

    if issue_number in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[issue_number]

    if issue_number in SPLIT_ISSUES:
        return SPLIT_ISSUES[issue_number]["new_title"]

    prefix = get_prefix(issue_type)

    if issue_type == "user-story":
        cleaned = clean_title(title)

        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        return f"{prefix} {cleaned}"

    return f"{prefix} {title}"


def get_priority(issue_number: int, milestone: str | None) -> str:
    """
    Regra inicial.
    Depois revisaremos manualmente caso a caso.
    """

    if milestone == "V1":
        if 9 <= issue_number <= 33:
            return "P0"
        return "P1"

    if milestone == "V2":
        return "P1"

    return "P2"


def get_size(body: str) -> str:
    """
    Tenta aproveitar o SP existente na EAP.
    """

    match = re.search(
        r"\|\s*SP final\s*\|\s*(\d+)\s*\|",
        body,
        flags=re.IGNORECASE,
    )

    if not match:
        return "M"

    points = int(match.group(1))

    if points <= 2:
        return "XS"

    if points <= 3:
        return "S"

    if points <= 5:
        return "M"

    if points <= 8:
        return "L"

    return "XL"


def extract_eap_id(body: str) -> str | None:
    match = re.search(
        r"\|\s*ID EAP\s*\|\s*([^|]+)\|",
        body,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def determine_action(issue_number: int, state: str) -> str:
    # Concluídas devem ser preservadas.
    if state.upper() == "CLOSED":
        return "keep"

    if issue_number in SPLIT_ISSUES:
        return "split"

    return "rewrite"


# =========================================================
# LEITURA
# =========================================================

def load_json_file(path: Path):
    """
    Carrega JSON exportado tanto em UTF-8 quanto UTF-16.

    PowerShell pode gerar arquivos UTF-16 dependendo
    da forma utilizada para redirecionar a saída.
    """

    raw = path.read_bytes()

    # UTF-16 LE
    if raw.startswith(b"\xff\xfe"):
        text = raw.decode("utf-16")

    # UTF-16 BE
    elif raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")

    # UTF-8 com BOM
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")

    # UTF-8 normal
    else:
        text = raw.decode("utf-8")

    return json.loads(text)


issues = load_json_file(ISSUES_FILE)
project_data = load_json_file(PROJECT_ITEMS_FILE)


project_items = project_data.get("items", [])

project_by_number = {}

for item in project_items:
    content = item.get("content") or {}
    number = content.get("number")

    if number is not None:
        project_by_number[number] = item


# =========================================================
# GERAÇÃO DO MAPA
# =========================================================

migration_map = []


for issue in sorted(
    issues,
    key=lambda item: item["number"],
):

    number = issue["number"]
    current_title = issue["title"]
    body = issue.get("body") or ""
    state = issue["state"]

    project_item = project_by_number.get(number, {})

    milestone = get_milestone(number)
    issue_type = get_type(number)
    action = determine_action(number, state)

    entry = {
        "source_issue": number,
        "eap": extract_eap_id(body),
        "current_title": current_title,
        "current_state": state,
        "current_project_status": project_item.get("status"),
        "action": action,
        "new_title": generate_new_title(
            number,
            current_title,
            issue_type,
        ),
        "type": issue_type,
        "milestone": milestone,
        "priority": get_priority(
            number,
            milestone,
        ),
        "size": get_size(body),
        "preserve_issue": True,
        "source_url": issue.get("url"),
    }

    if issue_number_data := SPLIT_ISSUES.get(number):
        entry["children"] = [
            {
                "key": None,
                "title": title,
                "milestone": milestone,
                "priority": get_priority(
                    number,
                    milestone,
                ),
                "parent_issue": number,
                "created_issue": None,
                "created_url": None,
            }
            for title in issue_number_data["children"]
        ]

    migration_map.append(entry)


# =========================================================
# ESCRITA
# =========================================================

with OUTPUT_FILE.open(
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        migration_map,
        file,
        ensure_ascii=False,
        indent=2,
    )


print(
    f"Migration map criado com "
    f"{len(migration_map)} issues."
)

print(f"Arquivo: {OUTPUT_FILE}")