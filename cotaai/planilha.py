"""Gera a planilha Excel final: abas Materiais e Serviços (+ Notas da IA)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

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
FONTE_CABECALHO = Font(bold=True, color="FFFFFF")
BORDA = Border(*(Side(style="thin", color="BFBFBF"),) * 4)


def _sim_nao(v: bool) -> str:
    return "Sim" if v else "Não (sugerido)"


def _aba(ws, colunas: list[tuple[str, int]], linhas: list[list], nome_tabela: str,
         status_col: int | None) -> None:
    ws.append([c for c, _ in colunas])
    for i, (_, largura) in enumerate(colunas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = largura
        celula = ws.cell(row=1, column=i)
        celula.fill = CABECALHO
        celula.font = FONTE_CABECALHO
        celula.alignment = Alignment(wrap_text=True, vertical="center")
    for linha in linhas:
        ws.append(linha)
    for r in range(2, ws.max_row + 1):
        for c in range(1, len(colunas) + 1):
            cel = ws.cell(row=r, column=c)
            cel.alignment = Alignment(wrap_text=True, vertical="top")
            cel.border = BORDA
        if status_col is not None:
            status_raw = linhas[r - 2][-1]
            cor = COR_STATUS.get(status_raw)
            if cor:
                for c in range(1, len(colunas) + 1):
                    ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=cor)
    # A última coluna (status bruto) é só auxiliar: escondida.
    ws.column_dimensions[get_column_letter(len(colunas))].hidden = True
    ws.freeze_panes = "C2"
    ws.row_dimensions[1].height = 32
    if linhas:
        ref = f"A1:{get_column_letter(len(colunas))}{ws.max_row}"
        tabela = Table(displayName=nome_tabela, ref=ref)
        tabela.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
        ws.add_table(tabela)


def gerar_planilha(final: dict, destino: Path, nome_projeto: str) -> Path:
    wb = Workbook()

    # ---------------- Materiais ----------------
    ws = wb.active
    ws.title = "Materiais"
    col_m = [
        ("Item", 7), ("Etapa da obra", 18), ("Material", 32), ("Especificação", 42),
        ("Especificado no projeto?", 13), ("Unid.", 7), ("Qtd. líquida", 11),
        ("Perda %", 8), ("Qtd. p/ compra", 12), ("Memória de cálculo", 40),
        ("Referência no projeto", 22), ("Observações", 32), ("Validação", 18),
        ("Nota da validação", 40), ("_status", 4),
    ]
    linhas = []
    for i, m in enumerate(final.get("materiais", []), start=2):
        linhas.append([
            m["id"], m["etapa_obra"], m["descricao"], m["especificacao"],
            _sim_nao(m["especificado_no_projeto"]), m["unidade"], m["quantidade"],
            m["perda_percentual"] / 100,
            f"=ROUNDUP(G{i}*(1+H{i}),2)",
            m["memoria_calculo"], m["referencia_projeto"], m["observacoes"],
            STATUS_LEGIVEL.get(m["status"], m["status"]), m["nota_validacao"], m["status"],
        ])
    _aba(ws, col_m, linhas, "Materiais", status_col=15)
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=7).number_format = "#,##0.00"
        ws.cell(row=r, column=8).number_format = "0%"
        ws.cell(row=r, column=9).number_format = "#,##0.00"

    # ---------------- Serviços ----------------
    ws = wb.create_sheet("Serviços")
    col_s = [
        ("Item", 7), ("Serviço", 34), ("Área de atuação", 20), ("Local de aplicação", 24),
        ("Escopo", 40), ("Especificado no projeto?", 13), ("Unid.", 7), ("Quantidade", 11),
        ("Valor unitário (cotar)", 13), ("Memória de cálculo", 40),
        ("Referência no projeto", 22), ("Observações", 32), ("Validação", 18),
        ("Nota da validação", 40), ("_status", 4),
    ]
    linhas = []
    for s in final.get("servicos", []):
        linhas.append([
            s["id"], s["servico"], s["area_atuacao"], s["local_aplicacao"],
            s["descricao_escopo"], _sim_nao(s["especificado_no_projeto"]), s["unidade"],
            s["quantidade"], None, s["memoria_calculo"], s["referencia_projeto"],
            s["observacoes"], STATUS_LEGIVEL.get(s["status"], s["status"]),
            s["nota_validacao"], s["status"],
        ])
    _aba(ws, col_s, linhas, "Servicos", status_col=15)
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=8).number_format = "#,##0.00"
        ws.cell(row=r, column=9).number_format = '"R$" #,##0.00'

    # ---------------- Notas da IA ----------------
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
    secao("Legenda de cores", [
        ["Amarelo", "Item corrigido pela validação/revisão"],
        ["Azul", "Item adicionado pela validação (etapa 2)"],
        ["Verde", "Item adicionado na revisão final (etapa 3)"],
    ])
    ws.append(["Atenção", "Quantitativos gerados por IA a partir do projeto. Confira os itens "
               "críticos antes de fechar contratos."])
    ws.cell(row=ws.max_row, column=1).font = negrito

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino
