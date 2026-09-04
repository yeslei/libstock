V1_REFINEMENTS = {
    16: {
        "persona": "funcionário responsável pelo acervo",
        "goal": "cadastrar uma obra",
        "benefit": (
            "manter o catálogo atualizado e permitir "
            "sua posterior consulta"
        ),
        "acceptance_criteria": [
            "Um usuário autorizado deve conseguir cadastrar uma nova obra.",
            "Os campos obrigatórios devem ser validados.",
            "O ano de publicação deve respeitar os limites do domínio.",
            "Falhas não devem deixar registros parcialmente persistidos.",
            "A obra cadastrada deve poder ser posteriormente consultada.",
        ],
        "business_rules": [
            "Uma obra representa o registro bibliográfico.",
            "Exemplares físicos são cadastrados separadamente.",
            "Uma obra pode possuir vários exemplares.",
        ],
        "open_questions": [],
    },
}