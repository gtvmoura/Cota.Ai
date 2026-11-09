"""Teste de ponta a ponta sem chamar a API (as três etapas são simuladas).

Executar:  python -m pytest -q   (ou: python tests/test_pipeline.py)
"""

import copy
import json
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cotaai import agentes, pipeline  # noqa: E402
from cotaai.schema import LEVANTAMENTO_SCHEMA  # noqa: E402

ETAPA1 = {
    "resumo_projeto": "Residência térrea, 120 m², arquitetônico apenas",
    "materiais": [{
        "id": "M001", "etapa_obra": "Alvenaria", "descricao": "Bloco cerâmico",
        "especificacao": "Bloco cerâmico vedação 14x19x29 cm", "especificado_no_projeto": True,
        "unidade": "un", "quantidade": 3000, "perda_percentual": 5,
        "memoria_calculo": "180 m² x 16,7 un/m²", "referencia_projeto": "Prancha 01",
        "observacoes": "", "status": "extraido", "nota_validacao": "",
    }],
    "servicos": [{
        "id": "S001", "servico": "Execução de alvenaria de vedação", "area_atuacao": "Alvenaria",
        "local_aplicacao": "Paredes internas e externas", "descricao_escopo": "Assentamento de blocos",
        "especificado_no_projeto": True, "unidade": "m²", "quantidade": 180,
        "memoria_calculo": "perímetro x pé-direito - vãos", "referencia_projeto": "Prancha 01",
        "observacoes": "", "status": "extraido", "nota_validacao": "",
    }],
    "itens_removidos": [], "premissas": ["Pé-direito 2,80 m"], "pendencias": [],
}


def _etapa2():
    e = copy.deepcopy(ETAPA1)
    e["materiais"][0].update(status="corrigido", quantidade=3010, nota_validacao="3000 → 3010")
    e["servicos"][0].update(status="confirmado", nota_validacao="ok")
    return e


def _etapa3():
    e = _etapa2()
    e["materiais"].append({**ETAPA1["materiais"][0], "id": "M002", "descricao": "Argamassa",
                           "especificacao": "Não especificado — argamassa 1:2:8", "unidade": "m³",
                           "quantidade": 2.5, "especificado_no_projeto": False,
                           "status": "adicionado_revisao_final", "nota_validacao": "faltava"})
    e["pendencias"].append("Confirmar tipo de telha")
    e["itens_removidos"].append({"id": "M099", "descricao": "Duplicado", "motivo": "duplicidade"})
    return e


def _exigidos(schema, dado, caminho="raiz"):
    """Confere campos obrigatórios/extras contra o esquema (validação simples)."""
    if schema["type"] == "object":
        assert set(dado) == set(schema["required"]), f"{caminho}: {set(dado) ^ set(schema['required'])}"
        for k, sub in schema["properties"].items():
            _exigidos(sub, dado[k], f"{caminho}.{k}")
    elif schema["type"] == "array":
        for i, item in enumerate(dado):
            _exigidos(schema["items"], item, f"{caminho}[{i}]")


def test_pipeline_completo(tmp_path, monkeypatch):
    chamadas = []

    def falso(client, blocos, instrucao, etapa):
        chamadas.append((etapa, blocos, instrucao))
        return {"1/3 extrator": ETAPA1, "2/3 validador": _etapa2(),
                "3/3 revisor final": _etapa3()}[etapa]

    monkeypatch.setattr(agentes, "_chamar", falso)

    for dado in (ETAPA1, _etapa2(), _etapa3()):
        _exigidos(LEVANTAMENTO_SCHEMA, dado)

    proj = tmp_path / "projetos" / "casa-teste"
    proj.mkdir(parents=True)
    (proj / "memorial.txt").write_text("Paredes em bloco cerâmico 14 cm. Área 120 m².", encoding="utf-8")
    (proj / "planta.dwg").write_bytes(b"x")  # deve ser ignorado

    saida = tmp_path / "cotacoes"
    assert pipeline.projetos_pendentes(tmp_path / "projetos", saida) == [proj]

    xlsx = pipeline.processar(proj, saida, client=object())
    assert [c[0] for c in chamadas] == ["1/3 extrator", "2/3 validador", "3/3 revisor final"]
    # O projeto vai em todas as etapas, com o mesmo prefixo (cache).
    assert chamadas[0][1] is chamadas[2][1]
    assert chamadas[0][1][-1]["cache_control"]["type"] == "ephemeral"
    assert "memorial.txt" in json.dumps(chamadas[0][1])
    assert "planta.dwg" not in json.dumps(chamadas[0][1])
    # O revisor recebe as duas etapas anteriores.
    assert "3000 → 3010" in chamadas[2][2] and '"extraido"' in chamadas[2][2]

    wb = load_workbook(xlsx)
    assert wb.sheetnames == ["Materiais", "Serviços", "Notas da IA"]
    m = wb["Materiais"]
    assert m["C2"].value == "Bloco cerâmico" and m["G2"].value == 3010
    assert m["I2"].value == "=ROUNDUP(G2*(1+H2),2)"
    assert m["E3"].value == "Não (sugerido)" and m["M3"].value == "Adicionado na revisão final"
    s = wb["Serviços"]
    assert s["B2"].value == "Execução de alvenaria de vedação" and s["C2"].value == "Alvenaria"
    assert s["H2"].value == 180 and s["I2"].value is None  # valor fica em branco para cotar
    notas = "\n".join(str(c.value) for row in wb["Notas da IA"].iter_rows() for c in row if c.value)
    assert "Confirmar tipo de telha" in notas and "duplicidade" in notas

    # Rodar de novo não chama a IA (nada mudou) e nada fica pendente.
    chamadas.clear()
    assert pipeline.projetos_pendentes(tmp_path / "projetos", saida) == []
    pipeline.processar(proj, saida, client=object())
    assert chamadas == []

    # Alterar o projeto refaz as três etapas.
    (proj / "memorial.txt").write_text("Paredes em bloco de concreto.", encoding="utf-8")
    assert pipeline.projetos_pendentes(tmp_path / "projetos", saida) == [proj]
    pipeline.processar(proj, saida, client=object())
    assert len(chamadas) == 3


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
