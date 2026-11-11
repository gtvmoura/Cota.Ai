"""Gera a planilha Excel final.

Sem preços:  abas Materiais, Serviços e Notas da IA.
Com preços:  Materiais (com colunas de preço), Serviços, Preços (detalhe), Lojas consultadas
             e Notas da IA.

Na aba "Preços (detalhe)" cada cotação tem a coluna "Considerar" (Sim/Não). Os preços mínimo,
médio e máximo e os totais da aba Materiais são fórmulas sobre as linhas marcadas "Sim": mudar um
"Sim" para "Não" (ou corrigir um preço) atualiza tudo.
"""

from __future__ import annotations

import math
import re
import zipfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from . import precos as P

STATUS_LEGIVEL = {
    "extraido": "Extraído",
    "confirmado": "Confirmado",
    "corrigido": "Corrigido",
    "adicionado_validacao": "Adicionado na validação",
    "adicionado_revisao_final": "Adicionado na revisão final",
}
COR_STATUS = {
    "corrigido": "FFF2CC",
    "adicionado_validacao": "DDEBF7",
    "adicionado_revisao_final": "E2EFDA",
}

CABECALHO = PatternFill("solid", fgColor="1F3864")
CABECALHO_PRECO = PatternFill("solid", fgColor="7F4F00")
FONTE_CABECALHO = Font(bold=True, color="FFFFFF")
BORDA = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
DET = "Preços (detalhe)"
LIMITE = 3000  # linhas consideradas nas fórmulas da aba de detalhe

# Resultado de cada fórmula, calculado aqui e gravado junto com ela. Sem isso, programas que não
# recalculam (visualizador, modo protegido, celular) mostram a célula em branco.
_CACHE: dict[tuple[str, str], object] = {}


def _guardar(aba: str, coord: str, valor) -> None:
    _CACHE[(aba, coord)] = valor


def _injetar_cache(arquivo: Path, abas: list[str]) -> None:
    """Grava no .xlsx o valor calculado de cada fórmula (o Excel ainda recalcula ao abrir)."""
    def aplicar(xml: str, aba: str) -> str:
        def troca(mo):
            coord, attrs, formula = mo.group(1), mo.group(2), mo.group(3)
            if (aba, coord) not in _CACHE:
                return mo.group(0)
            v = _CACHE[(aba, coord)]
            if isinstance(v, str):
                return f'<c r="{coord}"{attrs} t="str"><f>{formula}</f><v>{escape(v)}</v></c>'
            return f'<c r="{coord}"{attrs}><f>{formula}</f><v>{repr(float(v))}</v></c>'
        return re.sub(r'<c r="([A-Z]+\d+)"((?: s="\d+")?)><f>(.*?)</f>(?:<v></v>|<v ?/>)</c>', troca, xml)

    tmp = arquivo.with_suffix(".tmp")
    with zipfile.ZipFile(arquivo) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            dados = zin.read(item.filename)
            m = re.fullmatch(r"xl/worksheets/sheet(\d+)\.xml", item.filename)
            if m:
                dados = aplicar(dados.decode("utf-8"), abas[int(m.group(1)) - 1]).encode("utf-8")
            zout.writestr(item, dados)
    tmp.replace(arquivo)


def _sim_nao(v: bool) -> str:
    return "Sim" if v else "Não (sugerido)"


def _r(col: str) -> str:
    """Intervalo de uma coluna da aba de detalhe, para as fórmulas."""
    return f"'{DET}'!${col}$2:${col}${LIMITE}"


def _aba(ws, colunas, linhas, nome_tabela, cor_por_status=True, destaque=(), congelar="C2"):
    """Escreve cabeçalho e linhas. Se cor_por_status, a última coluna guarda o status bruto
    (oculta) e define a cor da linha. `destaque`: colunas (1..n) com cabeçalho na cor de preços."""
    ws.append([c for c, _ in colunas])
    for i, (_, largura) in enumerate(colunas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = largura
        celula = ws.cell(row=1, column=i)
        celula.fill = CABECALHO_PRECO if i in destaque else CABECALHO
        celula.font = FONTE_CABECALHO
        celula.alignment = Alignment(wrap_text=True, vertical="center")
    for linha in linhas:
        ws.append(linha)
    for r in range(2, ws.max_row + 1):
        for c in range(1, len(colunas) + 1):
            cel = ws.cell(row=r, column=c)
            cel.alignment = Alignment(wrap_text=True, vertical="top")
            cel.border = BORDA
        if cor_por_status:
            cor = COR_STATUS.get(linhas[r - 2][-1])
            if cor:
                for c in range(1, len(colunas) + 1):
                    ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=cor)
    if cor_por_status:
        ws.column_dimensions[get_column_letter(len(colunas))].hidden = True
    ws.freeze_panes = congelar
    ws.row_dimensions[1].height = 34
    if linhas:
        ref = f"A1:{get_column_letter(len(colunas))}{ws.max_row}"
        tabela = Table(displayName=nome_tabela, ref=ref)
        tabela.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
        ws.add_table(tabela)


def _formatar(ws, formatos: dict[int, str]) -> None:
    for r in range(2, ws.max_row + 1):
        for col, fmt in formatos.items():
            ws.cell(row=r, column=col).number_format = fmt


# ------------------------------------------------------------------------------------------
def _reais(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _arred2(v: float) -> float:
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _precos_por_loja(item) -> str:
    """Texto com o preço de cada loja, visível em qualquer programa (não depende de fórmula)."""
    if not item or not item["cotacoes"]:
        return ""
    partes = []
    for c in sorted(item["cotacoes"], key=lambda c: c["preco_unitario"]):
        marca = []
        if c["equivalencia"] == "aproximada":
            marca.append("aprox.")
        elif c["equivalencia"] == "similar":
            marca.append("similar")
        if c["disponibilidade"] == "sem estoque":
            marca.append("sem estoque")
        partes.append(f"{c['loja']} {_reais(c['preco_unitario'])}" + (f" ({', '.join(marca)})" if marca else ""))
    return " | ".join(partes)


def _aba_materiais(wb, final, precos_idx):
    ws = wb.active
    ws.title = "Materiais"
    materiais = final.get("materiais", [])
    n = len(materiais)
    com_preco = precos_idx is not None
    base = [
        ("Item", 7, "item"), ("Etapa da obra", 18, "etapa"), ("Material", 32, "mat"),
        ("Especificação", 42, "esp"), ("Especificado no projeto?", 13, "espproj"), ("Unid.", 7, "un"),
        ("Qtd. líquida", 11, "qtd"), ("Perda %", 8, "perda"), ("Qtd. p/ compra", 12, "compra"),
    ]
    preco = [
        ("Preço mín. (R$/un)", 12, "min"), ("Preço médio (R$/un)", 12, "med"), ("Preço máx. (R$/un)", 12, "max"),
        ("Cotações válidas", 10, "n"), ("Loja do menor preço", 20, "loja"),
        ("Preços por loja (R$/un)", 46, "porloja"), ("Lojas pesquisadas", 30, "pesq"),
        ("Total estimado, menor preço (R$)", 16, "tmin"), ("Total estimado, preço médio (R$)", 16, "tmed"),
        ("Situação do preço", 16, "sit"),
    ]
    adotado = [("Preço adotado (R$/un)", 14, "ad"), ("Total adotado (R$)", 16, "tad")]
    resto = [
        ("Memória de cálculo", 40, "mem"), ("Referência no projeto", 22, "ref"), ("Observações", 32, "obs"),
        ("Validação", 18, "val"), ("Nota da validação", 40, "nota"), ("_status", 4, "st"),
    ]
    specs = base + (preco if com_preco else []) + adotado + resto
    L = {chave: get_column_letter(k) for k, (_, _, chave) in enumerate(specs, start=1)}
    col = {chave: k for k, (_, _, chave) in enumerate(specs, start=1)}

    st = {"n_com_preco": 0, "soma_tmin": 0.0, "soma_tmed": 0.0, "soma_tad": 0.0, "n_tad": 0, "por_etapa": {}}
    linhas = []
    for i, m in enumerate(materiais, start=2):
        compra = math.ceil(m["quantidade"] * (1 + m["perda_percentual"] / 100) * 100 - 1e-9) / 100
        _guardar("Materiais", f"{L['compra']}{i}", compra)
        v = {
            "item": m["id"], "etapa": m["etapa_obra"], "mat": m["descricao"], "esp": m["especificacao"],
            "espproj": _sim_nao(m["especificado_no_projeto"]), "un": m["unidade"], "qtd": m["quantidade"],
            "perda": m["perda_percentual"] / 100,
            "compra": f"=ROUNDUP({L['qtd']}{i}*(1+{L['perda']}{i}),2)",
            "mem": m["memoria_calculo"], "ref": m["referencia_projeto"], "obs": m["observacoes"],
            "val": STATUS_LEGIVEL.get(m["status"], m["status"]), "nota": m["nota_validacao"], "st": m["status"],
        }
        medio_adotado = None
        if com_preco:
            item = precos_idx.get(m["id"])
            res = P.resumo_item(item) if item else None
            ok = bool(res and res["n"])
            crit = f'{_r("A")},${L["item"]}{i},{_r("K")},"Sim"'
            nn = f"{L['n']}{i}"
            v.update({
                "min": f'=IF({nn}=0,"",_xlfn.MINIFS({_r("H")},{crit}))',
                "med": f'=IF({nn}=0,"",AVERAGEIFS({_r("H")},{crit}))',
                "max": f'=IF({nn}=0,"",_xlfn.MAXIFS({_r("H")},{crit}))',
                "n": f"=COUNTIFS({crit})",
                "loja": res["loja_min"] if res else "",
                "porloja": _precos_por_loja(item),
                "pesq": ", ".join(item["lojas_pesquisadas"]) if item else "Não pesquisado",
                "tmin": f'=IF({L["min"]}{i}="","",{L["compra"]}{i}*{L["min"]}{i})',
                "tmed": f'=IF({L["med"]}{i}="","",{L["compra"]}{i}*{L["med"]}{i})',
                "sit": P.ROTULO_STATUS[item["status"]] if item else "Não pesquisado",
                "ad": f'=IF({L["med"]}{i}="","",ROUND({L["med"]}{i},2))',   # padrão: preço médio; digite por cima
            })
            for ch, val in (("min", res["min"] if ok else ""), ("med", res["medio"] if ok else ""),
                            ("max", res["max"] if ok else ""), ("n", res["n"] if res else 0),
                            ("tmin", compra * res["min"] if ok else ""), ("tmed", compra * res["medio"] if ok else "")):
                _guardar("Materiais", f"{L[ch]}{i}", val)
            if ok:
                st["n_com_preco"] += 1
                st["soma_tmin"] += compra * res["min"]
                st["soma_tmed"] += compra * res["medio"]
                medio_adotado = _arred2(res["medio"])
            _guardar("Materiais", f"{L['ad']}{i}", medio_adotado if medio_adotado is not None else "")
        else:
            v["ad"] = None                                  # preço adotado: a preencher
        v["tad"] = f'=IF({L["ad"]}{i}="","",{L["compra"]}{i}*{L["ad"]}{i})'
        if medio_adotado is not None:
            tad = compra * medio_adotado
            _guardar("Materiais", f"{L['tad']}{i}", tad)
            st["soma_tad"] += tad
            st["n_tad"] += 1
            st["por_etapa"][m["etapa_obra"]] = st["por_etapa"].get(m["etapa_obra"], 0.0) + tad
        else:
            _guardar("Materiais", f"{L['tad']}{i}", "")
        linhas.append([v[chave] for _, _, chave in specs])

    colunas = [(nome, larg) for nome, larg, _ in specs]
    destaque = tuple(col[k] for k in (["min", "med", "max", "n", "loja", "porloja", "pesq", "tmin", "tmed", "sit"]
                                      if com_preco else []) + ["ad", "tad"])
    _aba(ws, colunas, linhas, "Materiais", destaque=destaque)
    moeda = '"R$" #,##0.00'
    fmt = {col["qtd"]: "#,##0.00", col["perda"]: "0%", col["compra"]: "#,##0.00", col["ad"]: moeda, col["tad"]: moeda}
    if com_preco:
        fmt.update({col[k]: moeda for k in ("min", "med", "max", "tmin", "tmed")})
    _formatar(ws, fmt)
    return n, L, st


def _aba_servicos(wb, final):  # devolve o número de serviços
    ws = wb.create_sheet("Serviços")
    colunas = [
        ("Item", 7), ("Serviço", 34), ("Área de atuação", 20), ("Local de aplicação", 24),
        ("Escopo", 40), ("Especificado no projeto?", 13), ("Unid.", 7), ("Quantidade", 11),
        ("Valor unitário (cotar)", 13), ("Valor total (R$)", 14), ("Memória de cálculo", 40),
        ("Referência no projeto", 22), ("Observações", 32), ("Validação", 18),
        ("Nota da validação", 40), ("_status", 4),
    ]
    linhas = []
    for s in final.get("servicos", []):
        linhas.append([
            s["id"], s["servico"], s["area_atuacao"], s["local_aplicacao"],
            s["descricao_escopo"], _sim_nao(s["especificado_no_projeto"]), s["unidade"],
            s["quantidade"], None, f'=IF(I{len(linhas) + 2}="","",H{len(linhas) + 2}*I{len(linhas) + 2})',
            s["memoria_calculo"], s["referencia_projeto"],
            s["observacoes"], STATUS_LEGIVEL.get(s["status"], s["status"]),
            s["nota_validacao"], s["status"],
        ])
    for k in range(2, len(linhas) + 2):
        _guardar("Serviços", f"J{k}", "")                     # valor unitário em branco -> total vazio
    _aba(ws, colunas, linhas, "Servicos", destaque=(9, 10))
    _formatar(ws, {8: "#,##0.00", 9: '"R$" #,##0.00', 10: '"R$" #,##0.00'})
    return len(linhas)


def _aba_detalhe(wb, final, precos):
    ws = wb.create_sheet(DET)
    nomes = {m["id"]: m["descricao"] for m in final.get("materiais", [])}
    colunas = [
        ("Item", 7), ("Material", 30), ("Loja", 16), ("Produto encontrado", 44),
        ("Preço na loja (R$)", 13), ("Unid. de venda", 16), ("Conversão p/ unid. do orçamento", 26),
        ("Preço unitário (R$/un)", 13), ("Equivalência", 12), ("Disponibilidade", 13),
        ("Considerar", 11), ("Método", 10), ("Data", 11), ("Fonte (link)", 40), ("Observação", 36),
    ]
    linhas = []
    for it in precos["itens"]:
        for c in sorted(it["cotacoes"], key=lambda c: c["preco_unitario"]):
            if P.fora_do_padrao(it, c):
                c = dict(c, observacao=("Preço muito diferente das demais lojas: confira. " + c["observacao"]).strip())
            linhas.append([
                it["id"], nomes.get(it["id"], ""), c["loja"], c["produto_encontrado"],
                c["preco_embalagem"], c["unidade_venda"], c["conversao"], c["preco_unitario"],
                c["equivalencia"].capitalize(), c["disponibilidade"].capitalize(),
                "Sim" if P.considerar(c) else "Não",
                "Página do produto" if c["metodo"] == "pagina" else "Resultado de busca",
                c["data_referencia"], c["fonte"], c["observacao"],
            ])
    linhas.sort(key=lambda l: l[0])
    _aba(ws, colunas, linhas, "Precos", cor_por_status=False, destaque=(11,), congelar="D2")
    moeda = '"R$" #,##0.00'
    _formatar(ws, {5: moeda, 8: moeda})
    cinza = Font(color="808080")
    for r in range(2, ws.max_row + 1):
        url = ws.cell(row=r, column=14).value
        if url:
            ws.cell(row=r, column=14).hyperlink = url
            ws.cell(row=r, column=14).font = Font(color="0563C1", underline="single")
        if ws.cell(row=r, column=11).value == "Não":
            for c in (1, 2, 3, 4, 5, 8):
                ws.cell(row=r, column=c).font = cinza
    dv = DataValidation(type="list", formula1='"Sim,Não"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f"K2:K{max(ws.max_row, 2)}")


def _aba_lojas(wb, precos, n_mat, L, st):
    ws = wb.create_sheet("Lojas consultadas")
    for col, larg in zip("ABCDEFG", (28, 30, 46, 12, 12, 11, 60)):
        ws.column_dimensions[col].width = larg
    ws["A1"] = "Pesquisa de preços de mercado"
    ws["A1"].font = Font(bold=True, size=14)
    ult = n_mat + 1
    resumo = [
        ("Data da consulta", precos["data_consulta"]),
        ("Praça de referência", precos["regiao"]),
        ("Materiais com preço", f'=COUNTIF(Materiais!${L["n"]}$2:${L["n"]}${ult},">0")'),
        ("Materiais sem preço", f'={n_mat}-B5'),
        ("Total estimado, menor preço (R$)", f"=SUM(Materiais!${L['tmin']}$2:${L['tmin']}${ult})"),
        ("Total estimado, preço médio (R$)", f"=SUM(Materiais!${L['tmed']}$2:${L['tmed']}${ult})"),
    ]
    _guardar("Lojas consultadas", "B5", st["n_com_preco"])
    _guardar("Lojas consultadas", "B6", n_mat - st["n_com_preco"])
    _guardar("Lojas consultadas", "B7", st["soma_tmin"])
    _guardar("Lojas consultadas", "B8", st["soma_tmed"])
    for i, (k, v) in enumerate(resumo, start=3):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    ws["B7"].number_format = ws["B8"].number_format = '"R$" #,##0.00'
    ws["A9"] = ("Os totais somam só os materiais com preço encontrado: o valor real da obra é maior. "
                "Preços de sites variam por região, estoque e data. Confirme com a loja antes de fechar.")
    ws["A9"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A9:G9")
    ws.row_dimensions[9].height = 32

    cab = ["Loja", "Site", "Como foi consultada", "Itens pesquisados", "Itens com preço", "Cobertura", "Observação"]
    for c, t in enumerate(cab, start=1):
        cel = ws.cell(row=11, column=c, value=t)
        cel.fill, cel.font = CABECALHO, FONTE_CABECALHO
        cel.alignment = Alignment(wrap_text=True, vertical="center")
    for r, l in enumerate(precos["lojas"], start=12):
        ws.cell(row=r, column=1, value=l["loja"])
        ws.cell(row=r, column=2, value=l["dominio"] or "—")
        ws.cell(row=r, column=3, value=P.ROTULO_ACESSO[l["acesso"]])
        ws.cell(row=r, column=4, value=l["itens_pesquisados"])
        ws.cell(row=r, column=5, value=l["itens_com_preco"])
        ws.cell(row=r, column=6, value=f'=IF(D{r}=0,"",E{r}/D{r})').number_format = "0%"
        _guardar("Lojas consultadas", f"F{r}", l["itens_com_preco"] / l["itens_pesquisados"] if l["itens_pesquisados"] else "")
        ws.cell(row=r, column=7, value=l["observacao"])
        for c in range(1, 8):
            ws.cell(row=r, column=c).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=r, column=c).border = BORDA
        if l["acesso"] in ("sem_acesso", "sem_presenca_online"):
            for c in range(1, 8):
                ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor="FCE4D6")


def _aba_resumo(wb, final, n_mat, l_tot, n_serv, st):
    """Totais para conferir antes de montar a proposta comercial (fórmulas sobre os valores informados)."""
    ws = wb.create_sheet("Resumo financeiro")
    for col, larg in zip("ABC", (46, 20, 56)):
        ws.column_dimensions[col].width = larg
    ws["A1"] = "Resumo financeiro (preencha os valores nas abas Materiais e Serviços)"
    ws["A1"].font = Font(bold=True, size=14)
    moeda = '"R$" #,##0.00'
    um, us = n_mat + 1, n_serv + 1
    ws["A3"], ws["B3"] = "Materiais (preço adotado × quantidade para compra)", f"=SUM(Materiais!${l_tot}$2:${l_tot}${um})"
    ws["A4"], ws["B4"] = "Serviços (valor unitário × quantidade)", f"=SUM(Serviços!$J$2:$J${us})"
    ws["A5"], ws["B5"] = "Total geral", "=B3+B4"
    ws["A6"], ws["B6"] = "Materiais sem preço adotado", f'={n_mat}-COUNT(Materiais!${l_tot}$2:${l_tot}${um})'
    ws["A7"], ws["B7"] = "Serviços sem valor unitário", f'={n_serv}-COUNT(Serviços!$J$2:$J${us})'
    for coord, val in (("B3", st["soma_tad"]), ("B4", 0), ("B5", st["soma_tad"]), ("B6", n_mat - st["n_tad"]),
                       ("B7", n_serv)):
        _guardar("Resumo financeiro", coord, val)
    for r in (3, 4, 5):
        ws.cell(row=r, column=2).number_format = moeda
    for r in (3, 4, 5, 6, 7):
        ws.cell(row=r, column=1).font = Font(bold=(r == 5))
        ws.cell(row=r, column=2).font = Font(bold=(r == 5))
    ws["C6"] = "Itens sem preço ficam de fora do total: preencha antes de enviar a proposta."
    ws["C6"].alignment = ws["C7"].alignment = Alignment(wrap_text=True, vertical="top")

    def tabela(linha0, titulo, rotulos, aba, col_chave, col_val, n, valores):
        ws.cell(row=linha0, column=1, value=titulo).font = Font(bold=True, color="FFFFFF")
        ws.cell(row=linha0, column=1).fill = CABECALHO
        ws.cell(row=linha0, column=2, value="Total (R$)").font = Font(bold=True, color="FFFFFF")
        ws.cell(row=linha0, column=2).fill = CABECALHO
        for k, nome in enumerate(rotulos, start=linha0 + 1):
            ws.cell(row=k, column=1, value=nome)
            c = ws.cell(row=k, column=2,
                        value=f'=SUMIF({aba}!${col_chave}$2:${col_chave}${n + 1},A{k},{aba}!${col_val}$2:${col_val}${n + 1})')
            c.number_format = moeda
            _guardar("Resumo financeiro", f"B{k}", valores.get(nome, 0.0))
        return linha0 + len(rotulos) + 2

    areas = sorted({s["area_atuacao"] for s in final.get("servicos", [])})
    etapas = sorted({m["etapa_obra"] for m in final.get("materiais", [])})
    prox = tabela(9, "Serviços por área de atuação", areas, "Serviços", "C", "J", n_serv, {})
    tabela(prox, "Materiais por etapa da obra", etapas, "Materiais", "B", l_tot, n_mat, st["por_etapa"])


def _aba_notas(wb, final, nome_projeto, precos):
    ws = wb.create_sheet("Notas da IA")
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 110
    negrito = Font(bold=True)

    def secao(titulo, itens):
        ws.append([titulo])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12, color="1F3864")
        if not itens:
            ws.append(["", "—"])
        for item in itens:
            ws.append(item if isinstance(item, list) else ["", item])
            ws.cell(row=ws.max_row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        ws.append([])

    ws.append([f"Projeto: {nome_projeto}"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["Resumo", final.get("resumo_projeto", "")])
    ws.cell(row=2, column=1).font = negrito
    ws.cell(row=2, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.append([])
    secao("Pendências (confirmar antes de cotar)", final.get("pendencias", []))
    secao("Premissas adotadas", final.get("premissas", []))
    secao("Itens removidos na validação",
          [[r["id"], f'{r["descricao"]} — {r["motivo"]}'] for r in final.get("itens_removidos", [])])
    if precos:
        secao("Pesquisa de preços: observações", precos.get("observacoes_gerais", []))
        sem = [[i["id"], f'{i["termo_pesquisado"]} — {i["observacao"]}'] for i in precos["itens"]
               if i["status"] == "nao_encontrado"]
        secao("Materiais sem preço encontrado (cotar com fornecedor)", sem)
    secao("Legenda de cores", [
        ["Amarelo", "Item corrigido pela validação/revisão"],
        ["Azul", "Item adicionado pela validação (etapa 2)"],
        ["Verde", "Item adicionado na revisão final (etapa 3)"],
    ])
    ws.append(["Atenção", "Quantitativos e preços levantados por IA a partir do projeto e de sites de "
               "lojas. Confira os itens críticos antes de fechar contratos."])
    ws.cell(row=ws.max_row, column=1).font = negrito


# ------------------------------------------------------------------------------------------
def gerar_planilha(final: dict, destino: Path, nome_projeto: str, precos: dict | None = None) -> Path:
    _CACHE.clear()
    wb = Workbook()
    precos_idx = {i["id"]: i for i in precos["itens"]} if precos else None
    n_mat, L, st = _aba_materiais(wb, final, precos_idx)
    n_serv = _aba_servicos(wb, final)
    if precos:
        _aba_detalhe(wb, final, precos)
        _aba_lojas(wb, precos, n_mat, L, st)
    _aba_resumo(wb, final, n_mat, L["tad"], n_serv, st)
    _aba_notas(wb, final, nome_projeto, precos)
    wb.calculation = CalcProperties(fullCalcOnLoad=True)        # o Excel recalcula tudo ao abrir
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    _injetar_cache(destino, wb.sheetnames)
    return destino
