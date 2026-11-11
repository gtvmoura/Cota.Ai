"""Teste da etapa de preços com dados FICTÍCIOS (nenhuma consulta real)."""

import json
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cotaai import __main__ as cli  # noqa: E402
from cotaai import precos as P  # noqa: E402
from cotaai.planilha import gerar_planilha  # noqa: E402
from test_pipeline import ETAPA1, _etapa3  # noqa: E402


def _cot(loja, preco, **kw):
    base = dict(loja=loja, produto_encontrado=f"Bloco cerâmico ({loja})", preco_embalagem=preco * 10,
                unidade_venda="milheiro", conversao="milheiro = 1000 un", preco_unitario=preco,
                equivalencia="exata", disponibilidade="em estoque", metodo="pagina",
                data_referencia="2026-11-09", fonte=f"https://exemplo.test/{loja}/bloco", observacao="")
    base.update(kw)
    return base


def _lote(itens, lojas):
    return {"data_consulta": "2026-11-09", "regiao": "Teste/RJ (sem CEP)", "observacoes_gerais": ["dados fictícios"],
            "lojas": lojas, "itens": itens}


LOJA_A = dict(loja="Loja A", dominio="a.test", acesso="pagina_aberta", itens_pesquisados=2, itens_com_preco=1, observacao="")
LOJA_B = dict(loja="Loja B", dominio="b.test", acesso="somente_busca", itens_pesquisados=2, itens_com_preco=1, observacao="")
LOJA_C = dict(loja="Loja C", dominio="", acesso="sem_presenca_online", itens_pesquisados=2, itens_com_preco=0, observacao="sem site")


def test_precos_e_planilha(tmp_path):
    final = _etapa3()  # M001 bloco, M002 argamassa
    lote1 = _lote([{"id": "M001", "status": "encontrado", "termo_pesquisado": "bloco cerâmico 14x19x29",
                    "lojas_pesquisadas": ["Loja A", "Loja B", "Loja C"],
                    "cotacoes": [_cot("Loja A", 2.10), _cot("Loja B", 2.50),
                                 _cot("Loja B", 1.00, disponibilidade="sem estoque"),
                                 _cot("Loja A", 9.00, equivalencia="aproximada")],
                    "observacao": ""}], [LOJA_A, LOJA_B, LOJA_C])
    lote2 = _lote([{"id": "M002", "status": "nao_encontrado", "termo_pesquisado": "argamassa 1:2:8",
                    "lojas_pesquisadas": ["Loja A"], "cotacoes": [], "observacao": "só vendida a granel"}],
                  [dict(LOJA_A, itens_pesquisados=1, itens_com_preco=0)])
    assert P.validar(lote1) == [] and P.validar(lote2) == []

    mesclado = P.mesclar([lote1, lote2])
    assert [l["loja"] for l in mesclado["lojas"]] == ["Loja A", "Loja B", "Loja C"]
    assert mesclado["lojas"][0]["itens_pesquisados"] == 3
    assert mesclado["lojas"][1]["acesso"] == "somente_busca"
    assert P.validar(mesclado, {"M001", "M002"}) == []
    assert any("sem registro" in p for p in P.validar(mesclado, {"M001", "M002", "M003"}))

    res = P.resumo_item(mesclado["itens"][0])  # só as 2 cotações válidas entram
    assert res["n"] == 2 and res["min"] == 2.10 and res["max"] == 2.50 and res["loja_min"] == "Loja A"
    assert abs(res["medio"] - 2.30) < 1e-9

    # esquema recusa campo extra e id inexistente
    ruim = json.loads(json.dumps(mesclado)); ruim["itens"][0]["extra"] = 1
    assert P.validar(ruim)
    assert any("não existe" in p for p in P.validar(mesclado, {"M001"}))

    (tmp_path / "etapa3_final.json").write_text(json.dumps(final), encoding="utf-8")
    for n, l in enumerate((lote1, lote2), 1):
        (tmp_path / f"precos_lote{n}.json").write_text(json.dumps(l), encoding="utf-8")
    assert cli.main(["precos-mesclar", str(tmp_path / "precos_lote1.json"), str(tmp_path / "precos_lote2.json"),
                     "--final", str(tmp_path / "etapa3_final.json")]) == 0
    assert (tmp_path / "precos.json").exists()
    assert cli.main(["planilha", str(tmp_path / "etapa3_final.json")]) == 0

    wb = load_workbook(next(tmp_path.glob("*levantamento.xlsx")))
    assert wb.sheetnames == ["Materiais", "Serviços", "Preços (detalhe)", "Lojas consultadas", "Notas da IA"]
    m = wb["Materiais"]
    cab = [c.value for c in m[1]]
    assert cab[9:18] == ["Preço mín. (R$/un)", "Preço médio (R$/un)", "Preço máx. (R$/un)", "Cotações válidas",
                         "Loja do menor preço", "Lojas pesquisadas", "Total estimado, menor preço (R$)",
                         "Total estimado, preço médio (R$)", "Situação do preço"]
    assert "_xlfn.MINIFS" in m["J2"].value and "'Preços (detalhe)'" in m["J2"].value
    assert m["N2"].value == "Loja A" and m["O2"].value == "Loja A, Loja B, Loja C" and m["R2"].value == "Encontrado"
    assert m["R3"].value == "Não encontrado" and m["P2"].value == "=IF(J2=\"\",\"\",I2*J2)"
    d = wb["Preços (detalhe)"]
    assert d.max_row == 5  # 4 cotações do M001 + cabeçalho
    considerar = {(d.cell(r, 3).value, d.cell(r, 8).value): d.cell(r, 11).value for r in range(2, 6)}
    assert considerar[("Loja B", 1.0)] == "Não" and considerar[("Loja A", 9.0)] == "Não"
    assert considerar[("Loja A", 2.1)] == "Sim"
    assert d["N2"].hyperlink is not None
    lj = wb["Lojas consultadas"]
    textos = [str(c.value) for row in lj.iter_rows() for c in row if c.value]
    assert any("Somente resultado de busca" in t for t in textos)
    assert any("cotar por telefone ou WhatsApp" in t for t in textos)
    assert any("Teste/RJ" in t for t in textos)

    # sem preços a planilha continua no formato antigo
    assert cli.main(["planilha", str(tmp_path / "etapa3_final.json"), "--sem-precos",
                     "--destino", str(tmp_path / "sem.xlsx")]) == 0
    assert load_workbook(tmp_path / "sem.xlsx").sheetnames == ["Materiais", "Serviços", "Notas da IA"]
