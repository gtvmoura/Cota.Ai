"""Gera a planilha Excel final.

Sem preços:  abas Materiais, Serviços e Notas da IA.
Com preços:  Materiais (com colunas de preço), Serviços, Preços (detalhe), Lojas consultadas
             e Notas da IA.

Na aba "Preços (detalhe)" cada cotação tem a coluna "Considerar" (Sim/Não). Os preços mínimo,
médio e máximo e os totais da aba Materiais são fórmulas sobre as linhas marcadas "Sim": mudar um
"Sim" para "Não" (ou corrigir um preço) atualiza tudo.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
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
def _aba_materiais(wb, final, precos_idx):
    ws = wb.active
    ws.title = "Materiais"
    materiais = final.get("materiais", [])
    n = len(materiais)
    com_preco = precos_idx is not None
    base = [
        ("Item", 7), ("Etapa da obra", 18), ("Material", 32), ("Especificação", 42),
        ("Especificado no projeto?", 13), ("Unid.", 7), ("Qtd. líquida", 11),
        ("Perda %", 8), ("Qtd. p/ compra", 12),
    ]
    adotado = [("Preço adotado (R$/un)", 14), ("Total adotado (R$)", 16)]
    resto = [
        ("Memória de cálculo", 40), ("Referência no projeto", 22), ("Observações", 32),
        ("Validação", 18), ("Nota da validação", 40), ("_status", 4),
    ]
    preco_cols = [
        ("Preço mín. (R$/un)", 12), ("Preço médio (R$/un)", 12), ("Preço máx. (R$/un)", 12),
        ("Cotações válidas", 10), ("Loja do menor preço", 20), ("Lojas pesquisadas", 30),
        ("Total estimado, menor preço (R$)", 16), ("Total estimado, preço médio (R$)", 16),
        ("Situação do preço", 16),
    ]
    colunas = base + (preco_cols if com_preco else []) + adotado + resto
    c_ad = 19 if com_preco else 10          # coluna "Preço adotado" (S ou J)
    l_ad, l_tot = get_column_letter(c_ad), get_column_letter(c_ad + 1)

    linhas = []
    for i, m in enumerate(materiais, start=2):
        linha = [
            m["id"], m["etapa_obra"], m["descricao"], m["especificacao"],
            _sim_nao(m["especificado_no_projeto"]), m["unidade"], m["quantidade"],
            m["perda_percentual"] / 100,
            f"=ROUNDUP(G{i}*(1+H{i}),2)",
        ]
        if com_preco:
            item = precos_idx.get(m["id"])
            crit = f'{_r("A")},$A{i},{_r("K")},"Sim"'
            res = P.resumo_item(item) if item else None
            linha += [
                f'=IF(M{i}=0,"",_xlfn.MINIFS({_r("H")},{crit}))',
                f'=IF(M{i}=0,"",AVERAGEIFS({_r("H")},{crit}))',
                f'=IF(M{i}=0,"",_xlfn.MAXIFS({_r("H")},{crit}))',
                f"=COUNTIFS({crit})",
                res["loja_min"] if res else "",
                ", ".join(item["lojas_pesquisadas"]) if item else "Não pesquisado",
                f'=IF(J{i}="","",I{i}*J{i})',
                f'=IF(K{i}="","",I{i}*K{i})',
                P.ROTULO_STATUS[item["status"]] if item else "Não pesquisado",
                f'=IF(K{i}="","",ROUND(K{i},2))',   # padrão: preço médio; digite um valor para trocar
            ]
        else:
            linha += [None]                          # preço adotado: a preencher
        linha += [f'=IF({l_ad}{i}="","",I{i}*{l_ad}{i})']
        linha += [
            m["memoria_calculo"], m["referencia_projeto"], m["observacoes"],
            STATUS_LEGIVEL.get(m["status"], m["status"]), m["nota_validacao"], m["status"],
        ]
        linhas.append(linha)

    destaque = (tuple(range(10, 19)) if com_preco else ()) + (c_ad, c_ad + 1)
    _aba(ws, colunas, linhas, "Materiais", destaque=destaque)
    fmt = {7: "#,##0.00", 8: "0%", 9: "#,##0.00"}
    if com_preco:
        moeda = '"R$" #,##0.00'
        fmt.update({10: moeda, 11: moeda, 12: moeda, 16: moeda, 17: moeda})
    fmt.update({c_ad: '"R$" #,##0.00', c_ad + 1: '"R$" #,##0.00'})
    _formatar(ws, fmt)
    return n, l_tot


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


def _aba_lojas(wb, precos, n_mat):
    ws = wb.create_sheet("Lojas consultadas")
    for col, larg in zip("ABCDEFG", (28, 30, 46, 12, 12, 11, 60)):
        ws.column_dimensions[col].width = larg
    ws["A1"] = "Pesquisa de preços de mercado"
    ws["A1"].font = Font(bold=True, size=14)
    ult = n_mat + 1
    resumo = [
        ("Data da consulta", precos["data_consulta"]),
        ("Praça de referência", precos["regiao"]),
        ("Materiais com preço", f'=COUNTIF(Materiais!$M$2:$M${ult},">0")'),
        ("Materiais sem preço", f'={n_mat}-B5'),
        ("Total estimado, menor preço (R$)", f"=SUM(Materiais!$P$2:$P${ult})"),
        ("Total estimado, preço médio (R$)", f"=SUM(Materiais!$Q$2:$Q${ult})"),
    ]
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
        ws.cell(row=r, column=7, value=l["observacao"])
        for c in range(1, 8):
            ws.cell(row=r, column=c).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=r, column=c).border = BORDA
        if l["acesso"] in ("sem_acesso", "sem_presenca_online"):
            for c in range(1, 8):
                ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor="FCE4D6")


def _aba_resumo(wb, final, n_mat, l_tot, n_serv):
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
    for r in (3, 4, 5):
        ws.cell(row=r, column=2).number_format = moeda
    for r in (3, 4, 5, 6, 7):
        ws.cell(row=r, column=1).font = Font(bold=(r == 5))
        ws.cell(row=r, column=2).font = Font(bold=(r == 5))
    ws["C6"] = "Itens sem preço ficam de fora do total: preencha antes de enviar a proposta."
    ws["C6"].alignment = ws["C7"].alignment = Alignment(wrap_text=True, vertical="top")

    def tabela(linha0, titulo, rotulos, aba, col_chave, col_val, n):
        ws.cell(row=linha0, column=1, value=titulo).font = Font(bold=True, color="FFFFFF")
        ws.cell(row=linha0, column=1).fill = CABECALHO
        ws.cell(row=linha0, column=2, value="Total (R$)").font = Font(bold=True, color="FFFFFF")
        ws.cell(row=linha0, column=2).fill = CABECALHO
        for k, nome in enumerate(rotulos, start=linha0 + 1):
            ws.cell(row=k, column=1, value=nome)
            c = ws.cell(row=k, column=2,
                        value=f'=SUMIF({aba}!${col_chave}$2:${col_chave}${n + 1},A{k},{aba}!${col_val}$2:${col_val}${n + 1})')
            c.number_format = moeda
        return linha0 + len(rotulos) + 2

    areas = sorted({s["area_atuacao"] for s in final.get("servicos", [])})
    etapas = sorted({m["etapa_obra"] for m in final.get("materiais", [])})
    prox = tabela(9, "Serviços por área de atuação", areas, "Serviços", "C", "J", n_serv)
    tabela(prox, "Materiais por etapa da obra", etapas, "Materiais", "B", l_tot, n_mat)


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
    wb = Workbook()
    precos_idx = {i["id"]: i for i in precos["itens"]} if precos else None
    n_mat, l_tot = _aba_materiais(wb, final, precos_idx)
    n_serv = _aba_servicos(wb, final)
    if precos:
        _aba_detalhe(wb, final, precos)
        _aba_lojas(wb, precos, n_mat)
    _aba_resumo(wb, final, n_mat, l_tot, n_serv)
    _aba_notas(wb, final, nome_projeto, precos)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino
