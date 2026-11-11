"""Teste da proposta comercial com dados FICTÍCIOS."""

import datetime as dt
import json
import sys
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cotaai import __main__ as cli  # noqa: E402
from cotaai import proposta as PR  # noqa: E402
from cotaai.planilha import gerar_planilha  # noqa: E402
from test_pipeline import _etapa3  # noqa: E402


def test_por_extenso():
    ex = PR.por_extenso_brl
    assert ex(59800) == "cinquenta e nove mil e oitocentos reais"
    assert ex(1) == "um real" and ex(0) == "zero reais" and ex(100) == "cem reais" and ex(101) == "cento e um reais"
    assert ex(1000) == "mil reais" and ex(1250.5) == "mil duzentos e cinquenta reais e cinquenta centavos"
    assert ex(2_000_000) == "dois milhões de reais" and ex(1_000_001) == "um milhão e um reais"
    assert ex(21127.56) == "vinte e um mil cento e vinte e sete reais e cinquenta e seis centavos"
    assert ex(0.5) == "cinquenta centavos" and ex(0.01) == "um centavo"
    assert ex(59850) == "cinquenta e nove mil oitocentos e cinquenta reais"


def test_formatos():
    assert PR.brl(59800) == "R$ 59.800,00" and PR.brl(1234567.891) == "R$ 1.234.567,89"
    assert PR.pct(12.5) == "12,5%" and PR.pct(50) == "50%"
    assert PR.data_extenso(dt.date(2026, 8, 23), "Rio de Janeiro") == "Rio de Janeiro, 23 de Agosto de 2026."
    assert [PR._letra(i) for i in (0, 1, 25, 26)] == ["a", "b", "z", "aa"]
    assert [PR._romano(i) for i in (0, 1, 3, 8)] == ["i", "ii", "iv", "ix"]


EMPRESA = {
    "nome": "Empresa Teste", "logo": "", "cidade": "Rio de Janeiro", "prefixo_codigo": "CB",
    "responsavel": {"nome": "Fulano", "telefone": "21.90000-0000", "email": "f@x.test"},
    "rodape": ["@teste"], "consideracoes_gerais": ["Cláusula geral."],
    "pagamento_padrao": [{"rotulo": "SINAL", "percentual": 50, "quando": ""},
                         {"rotulo": "", "percentual": 25, "quando": "7 dias"},
                         {"rotulo": "Restante na entrega", "percentual": None, "quando": ""}],
    "responsabilidades": {"contratado": ["A"], "contratante": ["B"]},
    "inclusoes_padrao": ["Materiais incluídos"], "exclusoes_padrao": ["Licenças não incluídas"],
}


def _obra(tmp_path):
    final = _etapa3()
    final["servicos"].append(dict(final["servicos"][0], id="S002", servico="Pintura lisa",
                                  area_atuacao="Pintura", quantidade=210))
    (tmp_path / "etapa3_final.json").write_text(json.dumps(final), encoding="utf-8")
    x = tmp_path / "obra - levantamento.xlsx"
    gerar_planilha(final, x, "obra")
    wb = load_workbook(x)
    wb["Materiais"]["J2"], wb["Materiais"]["J3"] = 1.85, 38.0      # preço adotado dos materiais
    wb["Serviços"]["I2"], wb["Serviços"]["I3"] = 48.0, 22.0        # valor unitário dos serviços
    wb.save(x)
    return final, x


def test_valores_e_totais(tmp_path):
    _, x = _obra(tmp_path)
    v = PR.ler_valores(x)
    assert [m["qtd"] for m in v["materiais"]] == [3160.5, 2.63]    # quantidade p/ compra (com perda)
    c = PR.calcular(v, {"acrescimos": [{"descricao": "BDI", "percentual": 10}]})
    assert c["materiais"] == 5946.87 and c["servicos"] == 13260.0 and c["subtotal"] == 19206.87
    assert c["acrescimos"][0]["valor"] == 1920.69 and c["total"] == 21127.56 and not c["sem_preco"]
    assert PR.calcular(v, {"valor_final_manual": 20000})["total"] == 20000
    # item sem valor fica de fora e é avisado
    wb = load_workbook(x); wb["Serviços"]["I3"] = None; wb.save(x)
    assert PR.calcular(PR.ler_valores(x))["sem_valor"] == ["S002"]


def test_proposta_docx(tmp_path, monkeypatch):
    final, x = _obra(tmp_path)
    emp = tmp_path / "empresa.json"
    emp.write_text(json.dumps(EMPRESA), encoding="utf-8")
    assert cli.main(["proposta-init", str(tmp_path), "--empresa", str(emp)]) == 0
    cfg_p = tmp_path / "proposta" / "proposta.json"
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    assert (tmp_path / "proposta" / "proposta_conteudo.json").exists()
    cfg.update(numero=23, ano=2026, revisao=2, data="2026-11-12", tipo_obra="Reforma comercial",
               projeto_referencia="ARQ de 01/11/26", prazo_dias=28)
    cfg["cliente"] = {"nome": "CLIENTE TESTE", "aos_cuidados": "Sr. X", "telefone": "1", "email": "c@x.test"}
    cfg["valores"]["acrescimos"] = [{"descricao": "BDI", "percentual": 10}]
    cfg_p.write_text(json.dumps(cfg), encoding="utf-8")

    # rascunho: gera, com aviso visível
    assert cli.main(["proposta", str(tmp_path), "--empresa", str(emp)]) == 0
    arq = next((tmp_path / "proposta").glob("*RASCUNHO*.docx"))
    texto = "\n".join(p.text for p in Document(arq).paragraphs)
    cab = "\n".join(p.text for p in Document(arq).sections[0].header.paragraphs)
    assert "RASCUNHO" in cab and "CB023/2026 - CLIENTE TESTE - REV 02" in texto
    assert "R$ 21.127,56" in texto and "vinte e um mil cento e vinte e sete reais" in texto.lower()
    assert "SINAL de 50%" in texto and "25% a 7 dias" in texto and "Restante na entrega" in texto
    assert "Pintura lisa" in texto and "Licenças não incluídas" in texto and "Projeto Referencia : ARQ de 01/11/26" in texto

    # final sem "validado_por" é recusado; com ele, gera sem o selo de rascunho
    cfg["status"] = "final"
    cfg_p.write_text(json.dumps(cfg), encoding="utf-8")
    assert cli.main(["proposta", str(tmp_path), "--empresa", str(emp)]) == 1
    cfg["validado_por"] = "Fulano"
    cfg_p.write_text(json.dumps(cfg), encoding="utf-8")
    assert cli.main(["proposta", str(tmp_path), "--empresa", str(emp)]) == 0
    final_docx = next(p for p in (tmp_path / "proposta").glob("*.docx") if "RASCUNHO" not in p.name)
    assert "RASCUNHO" not in "\n".join(p.text for p in Document(final_docx).sections[0].header.paragraphs)
    # pagamento que não fecha 100% é recusado
    cfg["pagamento"] = [{"rotulo": "SINAL", "percentual": 50, "quando": ""}]
    assert any("somam" in e for e in PR.validar_proposta(cfg))
