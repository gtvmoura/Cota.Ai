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


# --------------------------------------------------------------------------------------
# Etapa 4: preços de mercado (pesquisa em lojas)
# --------------------------------------------------------------------------------------

ACESSO_LOJA = [
    "pagina_aberta",        # a página do produto foi aberta e o preço lido nela
    "somente_busca",        # preço lido no resultado de busca (pode estar desatualizado)
    "sem_acesso",           # site existe, mas não foi possível consultar
    "sem_presenca_online",  # não foi encontrado catálogo online: cotar por telefone/WhatsApp
]

STATUS_PRECO = ["encontrado", "parcial", "nao_encontrado", "nao_aplicavel"]

_COTACAO = {
    "type": "object",
    "properties": {
        "loja": {"type": "string"},
        "produto_encontrado": {"type": "string", "description": "Nome exato do anúncio/produto"},
        "preco_embalagem": {"type": "number", "description": "Preço mostrado na loja, em R$"},
        "unidade_venda": {"type": "string", "description": "Como é vendido: saco 50 kg, caixa 2,20 m², un, barra 6 m..."},
        "conversao": {
            "type": "string",
            "description": "Como o preço foi levado para a unidade do orçamento (ex.: 'caixa = 2,20 m²'); vazio se já está na unidade",
        },
        "preco_unitario": {"type": "number", "description": "R$ por UNIDADE DO ORÇAMENTO do item (já convertido)"},
        "equivalencia": {
            "type": "string",
            "enum": ["exata", "similar", "aproximada"],
            "description": "exata = mesma especificação; similar = mesma função e padrão; aproximada = alternativa menos próxima",
        },
        "disponibilidade": {"type": "string", "enum": ["em estoque", "sem estoque", "desconhecida"]},
        "metodo": {"type": "string", "enum": ["pagina", "busca"]},
        "data_referencia": {"type": "string", "description": "AAAA-MM-DD da validade/consulta do preço, ou vazio"},
        "fonte": {"type": "string", "description": "URL da página de onde o preço foi lido"},
        "observacao": {"type": "string"},
    },
    "required": [
        "loja", "produto_encontrado", "preco_embalagem", "unidade_venda", "conversao",
        "preco_unitario", "equivalencia", "disponibilidade", "metodo", "data_referencia",
        "fonte", "observacao",
    ],
    "additionalProperties": False,
}

_ITEM_PRECO = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "Id do material (M001...)"},
        "status": {"type": "string", "enum": STATUS_PRECO},
        "termo_pesquisado": {"type": "string"},
        "lojas_pesquisadas": {"type": "array", "items": {"type": "string"}},
        "cotacoes": {"type": "array", "items": _COTACAO},
        "observacao": {"type": "string"},
    },
    "required": ["id", "status", "termo_pesquisado", "lojas_pesquisadas", "cotacoes", "observacao"],
    "additionalProperties": False,
}

_LOJA = {
    "type": "object",
    "properties": {
        "loja": {"type": "string"},
        "dominio": {"type": "string"},
        "acesso": {"type": "string", "enum": ACESSO_LOJA},
        "itens_pesquisados": {"type": "number"},
        "itens_com_preco": {"type": "number"},
        "observacao": {"type": "string"},
    },
    "required": ["loja", "dominio", "acesso", "itens_pesquisados", "itens_com_preco", "observacao"],
    "additionalProperties": False,
}

PRECOS_SCHEMA = {
    "type": "object",
    "properties": {
        "data_consulta": {"type": "string", "description": "AAAA-MM-DD"},
        "regiao": {"type": "string", "description": "Praça de referência dos preços (ex.: Xerém/RJ) e se o site foi filtrado por CEP"},
        "observacoes_gerais": {"type": "array", "items": {"type": "string"}},
        "lojas": {"type": "array", "items": _LOJA},
        "itens": {"type": "array", "items": _ITEM_PRECO},
    },
    "required": ["data_consulta", "regiao", "observacoes_gerais", "lojas", "itens"],
    "additionalProperties": False,
}


def validar_schema(schema: dict, dado, caminho: str = "raiz") -> None:
    """Valida `dado` contra um esquema simples (object/array/string/number/boolean/enum).

    Levanta ValueError com o caminho do primeiro problema encontrado.
    """
    t = schema["type"]
    if t == "object":
        if not isinstance(dado, dict):
            raise ValueError(f"{caminho}: esperado objeto")
        faltam = set(schema["required"]) - set(dado)
        sobram = set(dado) - set(schema["required"])
        if faltam or sobram:
            raise ValueError(f"{caminho}: faltando {sorted(faltam)} / sobrando {sorted(sobram)}")
        for k, sub in schema["properties"].items():
            validar_schema(sub, dado[k], f"{caminho}.{k}")
    elif t == "array":
        if not isinstance(dado, list):
            raise ValueError(f"{caminho}: esperado lista")
        for i, item in enumerate(dado):
            validar_schema(schema["items"], item, f"{caminho}[{i}]")
    elif t == "string":
        if not isinstance(dado, str):
            raise ValueError(f"{caminho}: esperado texto")
        if "enum" in schema and dado not in schema["enum"]:
            raise ValueError(f"{caminho}: '{dado}' fora de {schema['enum']}")
    elif t == "number":
        if isinstance(dado, bool) or not isinstance(dado, (int, float)):
            raise ValueError(f"{caminho}: esperado número")
    elif t == "boolean":
        if not isinstance(dado, bool):
            raise ValueError(f"{caminho}: esperado verdadeiro/falso")
