"""Esquema JSON (structured outputs) compartilhado pelas três etapas.

Todas as etapas devolvem a MESMA estrutura, o que permite que o validador e o
revisor final reescrevam a lista inteira (corrigindo, adicionando e removendo
itens) e que a planilha seja gerada a partir de qualquer etapa.
"""

STATUS = [
    "extraido",                  # etapa 1 (extrator)
    "confirmado",                # validado sem alteração
    "corrigido",                 # quantidade/especificação/unidade ajustada
    "adicionado_validacao",      # incluído pela etapa 2
    "adicionado_revisao_final",  # incluído pela etapa 3
]

_MATERIAL = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "Código estável do item, ex.: M001"},
        "etapa_obra": {
            "type": "string",
            "description": "Etapa/grupo, ex.: Fundação, Estrutura, Alvenaria, Instalações Elétricas",
        },
        "descricao": {"type": "string", "description": "Nome do material"},
        "especificacao": {
            "type": "string",
            "description": "Especificação técnica (dimensão, classe, fck, bitola, marca/modelo, norma). "
            "Se o projeto não especificar, escreva a especificação usual sugerida e marque especificado_no_projeto=false",
        },
        "especificado_no_projeto": {"type": "boolean"},
        "unidade": {"type": "string", "description": "m², m³, m, kg, un, sc, cj, vb..."},
        "quantidade": {"type": "number", "description": "Quantidade líquida (sem perdas)"},
        "perda_percentual": {
            "type": "number",
            "description": "Perda/quebra sugerida em %, 0 se não se aplica",
        },
        "memoria_calculo": {
            "type": "string",
            "description": "Como a quantidade foi obtida (medidas, áreas, contagens)",
        },
        "referencia_projeto": {
            "type": "string",
            "description": "Prancha/página/legenda onde aparece, ou 'Não consta no projeto'",
        },
        "observacoes": {"type": "string"},
        "status": {"type": "string", "enum": STATUS},
        "nota_validacao": {
            "type": "string",
            "description": "O que foi conferido/alterado nesta etapa (vazio na etapa 1)",
        },
    },
    "required": [
        "id", "etapa_obra", "descricao", "especificacao", "especificado_no_projeto",
        "unidade", "quantidade", "perda_percentual", "memoria_calculo",
        "referencia_projeto", "observacoes", "status", "nota_validacao",
    ],
    "additionalProperties": False,
}

_SERVICO = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "Código estável do item, ex.: S001"},
        "servico": {"type": "string", "description": "Nome do serviço"},
        "area_atuacao": {
            "type": "string",
            "description": "Disciplina/especialidade, ex.: Terraplenagem, Estrutura, Alvenaria, "
            "Elétrica, Hidrossanitária, Impermeabilização, Pintura, Gesso/Drywall",
        },
        "local_aplicacao": {
            "type": "string",
            "description": "Ambiente/pavimento/elemento onde o serviço é executado",
        },
        "descricao_escopo": {"type": "string", "description": "Escopo resumido do serviço"},
        "especificado_no_projeto": {"type": "boolean"},
        "unidade": {"type": "string", "description": "m², m³, m, un, vb, mês..."},
        "quantidade": {"type": "number", "description": "Área/volume/extensão/quantidade do serviço"},
        "memoria_calculo": {"type": "string"},
        "referencia_projeto": {"type": "string"},
        "observacoes": {"type": "string"},
        "status": {"type": "string", "enum": STATUS},
        "nota_validacao": {"type": "string"},
    },
    "required": [
        "id", "servico", "area_atuacao", "local_aplicacao", "descricao_escopo",
        "especificado_no_projeto", "unidade", "quantidade", "memoria_calculo",
        "referencia_projeto", "observacoes", "status", "nota_validacao",
    ],
    "additionalProperties": False,
}

_REMOVIDO = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "descricao": {"type": "string"},
        "motivo": {"type": "string"},
    },
    "required": ["id", "descricao", "motivo"],
    "additionalProperties": False,
}

LEVANTAMENTO_SCHEMA = {
    "type": "object",
    "properties": {
        "resumo_projeto": {
            "type": "string",
            "description": "Tipo de obra, área construída, pavimentos, disciplinas recebidas",
        },
        "materiais": {"type": "array", "items": _MATERIAL},
        "servicos": {"type": "array", "items": _SERVICO},
        "itens_removidos": {
            "type": "array",
            "items": _REMOVIDO,
            "description": "Itens da etapa anterior retirados (duplicados, fora de escopo, errados)",
        },
        "premissas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Premissas adotadas onde o projeto é omisso",
        },
        "pendencias": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Dúvidas a confirmar com o cliente/projetista antes de cotar",
        },
    },
    "required": [
        "resumo_projeto", "materiais", "servicos", "itens_removidos", "premissas", "pendencias",
    ],
    "additionalProperties": False,
}
