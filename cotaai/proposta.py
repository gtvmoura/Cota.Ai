"""Proposta comercial: lê os valores informados na planilha validada e gera o documento (DOCX e PDF).

Fluxo:  planilha validada (preços e valores preenchidos)  +  proposta.json (dados da proposta)
        +  proposta_conteudo.json (memorial, observações e exclusões)  +  empresa.json (modelo da empresa)
        ->  <codigo> - PROPOSTA REV NN.docx / .pdf

O documento segue o modelo da empresa: ofício de abertura, memorial descritivo por disciplina,
observações e exclusões, considerações gerais, valor, prazo, pagamento, responsabilidades e assinatura.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import shutil
import subprocess
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openpyxl import load_workbook

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
         "Outubro", "Novembro", "Dezembro"]

# ------------------------------------------------------------------------------------------
# Formatação
# ------------------------------------------------------------------------------------------
_UN = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze",
       "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CEN = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
        "oitocentos", "novecentos"]


def _ate_999(n: int) -> str:
    if n == 100:
        return "cem"
    partes = []
    if n >= 100:
        partes.append(_CEN[n // 100])
        n %= 100
    if n:
        partes.append(_UN[n] if n < 20 else _DEZ[n // 10] + (f" e {_UN[n % 10]}" if n % 10 else ""))
    return " e ".join(partes)


def _inteiro_extenso(n: int) -> str:
    if n == 0:
        return "zero"
    grupos = [(n // 10**9, "bilhão", "bilhões"), ((n // 10**6) % 1000, "milhão", "milhões"),
              ((n // 10**3) % 1000, "mil", "mil"), (n % 1000, "", "")]
    itens = []
    for v, sing, plur in grupos:
        if not v:
            continue
        if sing == "mil":
            texto = "mil" if v == 1 else f"{_ate_999(v)} mil"
        elif sing:
            texto = f"{_ate_999(v)} {sing if v == 1 else plur}"
        else:
            texto = _ate_999(v)
        itens.append((v, texto))
    saida = itens[0][1]
    for i, (v, texto) in enumerate(itens[1:], start=1):
        ultimo = i == len(itens) - 1
        saida += (" e " if ultimo and (v < 100 or v % 100 == 0) else " ") + texto
    return saida


def por_extenso_brl(valor: float) -> str:
    """59800 -> 'cinquenta e nove mil e oitocentos reais'."""
    v = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    reais, centavos = int(v), int((v - int(v)) * 100)
    partes = []
    if reais or not centavos:
        txt = _inteiro_extenso(reais)
        de = " de" if reais >= 10**6 and reais % 10**6 == 0 else ""
        partes.append(f"{txt}{de} {'real' if reais == 1 else 'reais'}")
    if centavos:
        partes.append(f"{_inteiro_extenso(centavos)} {'centavo' if centavos == 1 else 'centavos'}")
    return " e ".join(partes)


def brl(valor: float) -> str:
    """59800 -> 'R$ 59.800,00'."""
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor: float) -> str:
    return (f"{valor:.2f}".rstrip("0").rstrip(".")).replace(".", ",") + "%"


def data_extenso(data: dt.date, cidade: str) -> str:
    return f"{cidade}, {data.day} de {MESES[data.month - 1]} de {data.year}."


def _letra(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(97 + r) + s
    return s


def _romano(i: int) -> str:
    n, saida = i + 1, ""
    for v, r in [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]:
        while n >= v:
            saida += r
            n -= v
    return saida


# ------------------------------------------------------------------------------------------
# Valores informados na planilha
# ------------------------------------------------------------------------------------------
def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _colunas(ws) -> dict[str, int]:
    return {str(c.value).strip(): i for i, c in enumerate(ws[1]) if c.value is not None}


def ler_valores(xlsx: Path, precos: dict | None = None) -> dict:
    """Lê quantidades e valores da planilha, que é a fonte de verdade depois da validação.

    Materiais: usa a coluna "Preço adotado". Se a planilha nunca foi calculada (sem valores em cache),
    cai no padrão da própria planilha: o preço médio das cotações marcadas "Considerar = Sim".
    Serviços: usa "Valor unitário (cotar)".
    """
    wf, wv = load_workbook(xlsx), load_workbook(xlsx, data_only=True)
    idx_precos = {i["id"]: i for i in precos["itens"]} if precos else {}
    from . import precos as P

    materiais, servicos = [], []
    wsf, wsv = wf["Materiais"], wv["Materiais"]
    col = _colunas(wsf)
    for r in range(2, wsf.max_row + 1):
        rf = [c.value for c in wsf[r]]
        rv = [c.value for c in wsv[r]]
        id_ = rf[col["Item"]]
        if not id_:
            continue
        qtd = _num(rf[col["Qtd. líquida"]]) or 0.0
        perda = _num(rf[col["Perda %"]]) or 0.0
        perda = perda / 100 if perda > 1 else perda
        preco = _num(rv[col["Preço adotado (R$/un)"]])
        if preco is None:
            preco = _num(rf[col["Preço adotado (R$/un)"]])
        if preco is None and id_ in idx_precos:
            res = P.resumo_item(idx_precos[id_])
            if res["n"] and isinstance(rf[col["Preço adotado (R$/un)"]], str):
                preco = round(res["medio"], 2)
        qtd_compra = math.ceil(qtd * (1 + perda) * 100 - 1e-9) / 100
        materiais.append({
            "id": id_, "nome": rf[col["Material"]], "grupo": rf[col["Etapa da obra"]],
            "unidade": rf[col["Unid."]], "qtd": qtd_compra, "preco": preco,
            "total": round(qtd_compra * preco, 2) if preco is not None else None,
        })
    wsf, wsv = wf["Serviços"], wv["Serviços"]
    col = _colunas(wsf)
    for r in range(2, wsf.max_row + 1):
        rf = [c.value for c in wsf[r]]
        id_ = rf[col["Item"]]
        if not id_:
            continue
        qtd = _num(rf[col["Quantidade"]]) or 0.0
        unit = _num(rf[col["Valor unitário (cotar)"]])
        servicos.append({
            "id": id_, "nome": rf[col["Serviço"]], "grupo": rf[col["Área de atuação"]],
            "unidade": rf[col["Unid."]], "qtd": qtd, "preco": unit,
            "total": round(qtd * unit, 2) if unit is not None else None,
        })
    return {"materiais": materiais, "servicos": servicos}


def calcular(valores: dict, cfg_valores: dict | None = None) -> dict:
    """Totais por grupo, acréscimos e total geral. `valor_final_manual` substitui o total calculado."""
    cfg = cfg_valores or {}
    mats = [m for m in valores["materiais"] if m["total"] is not None]
    servs = [s for s in valores["servicos"] if s["total"] is not None]
    tot_m = round(sum(m["total"] for m in mats), 2)
    por_area: dict[str, float] = {}
    for s in servs:
        por_area[s["grupo"]] = round(por_area.get(s["grupo"], 0) + s["total"], 2)
    tot_s = round(sum(por_area.values()), 2)
    subtotal = round(tot_m + tot_s, 2)
    acresc = []
    for a in cfg.get("acrescimos", []):
        if a.get("percentual"):
            acresc.append({"descricao": a["descricao"], "percentual": a["percentual"],
                           "valor": round(subtotal * a["percentual"] / 100, 2)})
    total_calc = round(subtotal + sum(a["valor"] for a in acresc), 2)
    total = cfg.get("valor_final_manual") or total_calc
    return {
        "materiais": tot_m, "servicos": tot_s, "servicos_por_area": por_area, "subtotal": subtotal,
        "acrescimos": acresc, "total_calculado": total_calc, "total": float(total),
        "manual": bool(cfg.get("valor_final_manual")),
        "sem_preco": [m["id"] for m in valores["materiais"] if m["total"] is None],
        "sem_valor": [s["id"] for s in valores["servicos"] if s["total"] is None],
    }


# ------------------------------------------------------------------------------------------
# Configuração e rascunho do conteúdo
# ------------------------------------------------------------------------------------------
def carregar_json(caminho: Path) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def validar_proposta(cfg: dict) -> list[str]:
    p = []
    if not cfg.get("numero") and not cfg.get("codigo"):
        p.append("informe 'numero' (e 'ano') ou 'codigo' da proposta")
    for campo in ("tipo_obra", "prazo_dias"):
        if not cfg.get(campo):
            p.append(f"falta '{campo}'")
    c = cfg.get("cliente", {})
    if not c.get("nome") or c["nome"].startswith("("):
        p.append("falta cliente.nome")
    if cfg.get("status") not in ("rascunho", "final"):
        p.append("status deve ser 'rascunho' ou 'final'")
    pag = cfg.get("pagamento") or []
    fixas = sum(x["percentual"] for x in pag if x.get("percentual") is not None)
    tem_resto = any(x.get("percentual") is None for x in pag)
    if pag and not tem_resto and abs(fixas - 100) > 0.01:
        p.append(f"as parcelas de pagamento somam {fixas:g}% (devem somar 100% ou ter uma parcela 'restante')")
    if fixas > 100.01:
        p.append("as parcelas de pagamento passam de 100%")
    return p


def validar_conteudo(c: dict) -> list[str]:
    """Confere a estrutura de proposta_conteudo.json (memorial, inclusões, exclusões)."""
    p = []
    mem = c.get("memorial")
    if not isinstance(mem, list) or not mem:
        return ["memorial vazio ou ausente"]
    for i, g in enumerate(mem, 1):
        if not isinstance(g, dict) or not g.get("titulo"):
            p.append(f"memorial[{i}] sem título")
            continue
        for j, it in enumerate(g.get("itens", []), 1):
            if not isinstance(it, dict) or not it.get("texto"):
                p.append(f"memorial[{i}].itens[{j}] sem texto")
            elif not isinstance(it.get("subitens", []), list):
                p.append(f"memorial[{i}].itens[{j}].subitens deve ser lista")
    for chave in ("inclusoes", "exclusoes", "consideracoes_adicionais"):
        if not isinstance(c.get(chave, []), list) or not all(isinstance(x, str) for x in c.get(chave, [])):
            p.append(f"'{chave}' deve ser uma lista de textos")
    return p


def codigo_proposta(cfg: dict, empresa: dict) -> str:
    if cfg.get("codigo"):
        return cfg["codigo"]
    ano = cfg.get("ano") or dt.date.fromisoformat(cfg["data"]).year
    return f"{empresa.get('prefixo_codigo', 'PC')}{int(cfg['numero']):03d}/{ano}"


def memorial_automatico(final: dict, empresa: dict) -> dict:
    """Rascunho do conteúdo a partir da lista final: um grupo por área de atuação dos serviços.

    É só o ponto de partida; o agente redator reescreve no estilo da proposta (itens curtos e
    sem quantidades) e confere inclusões e exclusões.
    """
    grupos: dict[str, list[str]] = {}
    for s in final.get("servicos", []):
        grupos.setdefault(s["area_atuacao"], [])
        if s["servico"] not in grupos[s["area_atuacao"]]:
            grupos[s["area_atuacao"]].append(s["servico"])
    excl = list(empresa.get("exclusoes_padrao", []))
    for r in final.get("itens_removidos", []):
        if any(k in r["motivo"].lower() for k in ("terceiro", "escopo", "franquia", "fornecimento")):
            excl.append(f"{r['descricao'].upper()}: NÃO FAZ PARTE DE NOSSO ESCOPO")
    return {
        "memorial": [{"titulo": g, "itens": [{"texto": t, "subitens": []} for t in itens]}
                     for g, itens in grupos.items()],
        "inclusoes": list(empresa.get("inclusoes_padrao", [])),
        "exclusoes": excl,
        "consideracoes_adicionais": [],
    }


# ------------------------------------------------------------------------------------------
# Documento
# ------------------------------------------------------------------------------------------
def _texto_parcela(p: dict, total: float, acumulado: float, mostrar_valor: bool) -> tuple[str, float]:
    rot, quando, perc = p.get("rotulo", ""), p.get("quando", ""), p.get("percentual")
    if perc is None:
        texto = rot or "Restante na entrega"
        valor = round(total - acumulado, 2)
    else:
        if rot:
            texto = f"{rot} de {pct(perc)}"
        elif quando:
            texto = f"{pct(perc)} {'a ' if quando[0].isdigit() else ''}{quando}"
        else:
            texto = pct(perc)
        valor = round(total * perc / 100, 2)
    if mostrar_valor:
        texto += f": {brl(valor)}"
    return texto, valor


def gerar_docx(empresa: dict, cfg: dict, conteudo: dict, calc: dict, destino: Path,
               raiz: Path | None = None) -> Path:
    from docx import Document
    from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    raiz = Path(raiz or ".")
    rascunho = cfg["status"] == "rascunho"
    cliente = cfg["cliente"]
    codigo = codigo_proposta(cfg, empresa)
    rev = int(cfg.get("revisao", 0))
    data = dt.date.fromisoformat(cfg["data"])

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.4)
    sec.top_margin, sec.bottom_margin = Cm(3.4), Cm(3.2)
    sec.header_distance, sec.footer_distance = Cm(0.8), Cm(0.6)

    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Arial", Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.25

    def par(texto="", negrito=False, sublinhado=False, alinhar=None, tamanho=None, recuo=None,
            antes=None, depois=None, cor=None, manter=False):
        p = doc.add_paragraph()
        if texto:
            r = p.add_run(texto)
            r.bold, r.underline = negrito, sublinhado
            if tamanho:
                r.font.size = Pt(tamanho)
            if cor:
                r.font.color.rgb = RGBColor.from_string(cor)
        if alinhar is not None:
            p.alignment = alinhar
        if recuo is not None:
            p.paragraph_format.left_indent = Cm(recuo)
        if antes is not None:
            p.paragraph_format.space_before = Pt(antes)
        if depois is not None:
            p.paragraph_format.space_after = Pt(depois)
        p.paragraph_format.keep_with_next = manter
        return p

    def marcador(texto, simbolo="▪", recuo=1.0, justificar=True):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(recuo + 0.6)
        p.paragraph_format.first_line_indent = Cm(-0.6)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(recuo + 0.6))
        p.add_run(f"{simbolo}\t{texto}")
        if justificar:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        return p

    def quebra():
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def sombra(cel, hexcor):
        pr = cel._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"), shd.set(qn("w:color"), "auto"), shd.set(qn("w:fill"), hexcor)
        pr.append(shd)

    # ----- cabeçalho (logo) e rodapé -----
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logo = Path(empresa.get("logo", ""))
    for cand in (logo, raiz / logo):
        if logo.name and cand.exists():
            hp.add_run().add_picture(str(cand), width=Cm(3.0))
            break
    if rascunho:
        r = sec.header.add_paragraph().add_run("RASCUNHO: valores ainda não validados. Não enviar ao cliente.")
        r.bold, r.font.size, r.font.color.rgb = True, Pt(9), RGBColor(0xC0, 0x00, 0x00)
        sec.header.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for k, linha in enumerate(empresa.get("rodape", [])):
        p = sec.footer.paragraphs[0] if k == 0 else sec.footer.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(linha)
        r.font.size = Pt(9)
    barra = sec.footer.add_table(rows=1, cols=1, width=sec.page_width - sec.left_margin - sec.right_margin)
    barra.alignment = WD_TABLE_ALIGNMENT.CENTER
    barra.rows[0].height, barra.rows[0].height_rule = Cm(0.35), WD_ROW_HEIGHT_RULE.EXACTLY
    sombra(barra.cell(0, 0), empresa.get("cor_barra", "4FB8E8"))

    # ----- página 1: ofício -----
    par(f"{codigo} - {cliente['nome'].upper()} - REV {rev:02d}", True, alinhar=WD_ALIGN_PARAGRAPH.RIGHT, tamanho=13)
    par(data_extenso(data, empresa.get("cidade", "")), alinhar=WD_ALIGN_PARAGRAPH.RIGHT, depois=18)
    par(f"À {cliente['nome'].upper()}", True, depois=0)
    if cliente.get("aos_cuidados"):
        par(f"ATT.: {cliente['aos_cuidados']}", True, depois=0)
    par(f"Tel.: {cliente.get('telefone', '')}", True, depois=0)
    par(f"Email.: {cliente.get('email', '')}", True, depois=0)
    par(f"Ref.: {cfg.get('referencia', 'Orçamento Serviço')}", True, depois=14)
    caixa = doc.add_table(rows=1, cols=1)
    caixa.style = "Table Grid"
    caixa.alignment = WD_TABLE_ALIGNMENT.CENTER
    cp = caixa.cell(0, 0).paragraphs[0]
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.space_before = cp.paragraph_format.space_after = Pt(6)
    cp.add_run(f"PROPOSTA COMERCIAL-REVISÃO {rev:02d}").bold = True
    par("", depois=10)
    par("Prezado Cliente.", depois=8)
    par(f"Em atendimento a vossa solicitação, apresentamos a seguir nosso escopo técnico/comercial "
        f"para {cfg['tipo_obra']}.", alinhar=WD_ALIGN_PARAGRAPH.JUSTIFY)

    # ----- memorial descritivo -----
    quebra()
    par("MEMORIAL DESCRITIVO:", True, depois=6, manter=True)
    for i, grupo in enumerate(conteudo["memorial"], start=1):
        par(f"{i}. {grupo['titulo']}", True, antes=4, depois=2, manter=True)
        for j, item in enumerate(grupo["itens"]):
            p = par(f"{_letra(j)}. {item['texto']}", recuo=0.9, depois=1)
            p.paragraph_format.first_line_indent = Cm(-0.5)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            for k, sub in enumerate(item.get("subitens", [])):
                q = par(f"{_romano(k)}. {sub}", recuo=2.0, depois=1)
                q.paragraph_format.first_line_indent = Cm(-0.5)
                q.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    par("OBSERVAÇÕES:", True, antes=10, depois=4, manter=True)
    if cfg.get("projeto_referencia"):
        marcador(f"Projeto Referencia : {cfg['projeto_referencia']}", "•", 0.3)
    for t in conteudo.get("inclusoes", []):
        marcador(t, "•", 0.3)
    if conteudo.get("exclusoes") or cfg.get("projeto_referencia"):
        par("OBSERVAÇÕES 2 – EXCLUSÕES:", True, antes=10, depois=4, manter=True)
        if cfg.get("projeto_referencia"):
            marcador(f"Projeto Referencia : {cfg['projeto_referencia']}", "•", 0.3)
        for t in conteudo.get("exclusoes", []):
            marcador(t, "•", 0.3)

    # ----- considerações gerais, valor, prazo e pagamento -----
    quebra()
    par("CONSIDERAÇÕES GERAIS", sublinhado=True, alinhar=WD_ALIGN_PARAGRAPH.CENTER, depois=10, manter=True)
    for t in list(empresa.get("consideracoes_gerais", [])) + list(conteudo.get("consideracoes_adicionais", [])):
        marcador(t, "▪", 0.4)
    par("PROPOSTA COMERCIAL", True, alinhar=WD_ALIGN_PARAGRAPH.CENTER, antes=16, depois=10, manter=True)
    par("VALOR TOTAL DOS SERVIÇOS:", True, alinhar=WD_ALIGN_PARAGRAPH.CENTER, depois=8, manter=True)
    total = calc["total"]
    cfg_v = cfg.get("valores", {})
    if cfg_v.get("modo", "global") == "detalhado":
        linhas = [("Materiais", calc["materiais"])]
        linhas += [(f"Mão de obra: {a}", v) for a, v in sorted(calc["servicos_por_area"].items())]
        linhas += [(a["descricao"] + f" ({pct(a['percentual'])})", a["valor"]) for a in calc["acrescimos"]]
        if calc["manual"]:
            linhas.append(("Ajuste comercial", round(total - calc["total_calculado"], 2)))
        tab = doc.add_table(rows=0, cols=2)
        tab.style = "Table Grid"
        tab.alignment = WD_TABLE_ALIGNMENT.CENTER
        for nome, v in linhas + [("TOTAL", total)]:
            c = tab.add_row().cells
            c[0].text, c[1].text = nome, brl(v)
            c[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if nome == "TOTAL":
                for x in c:
                    x.paragraphs[0].runs[0].bold = True
        par("", depois=2)
    else:
        rotulo = cfg_v.get("rotulo") or cfg["tipo_obra"].upper()
        par(rotulo, recuo=1.2, depois=0)
    par(f"{brl(total)} ( {por_extenso_brl(total).capitalize()} )", True, recuo=1.2, depois=8)
    if empresa.get("nota_valor"):
        marcador(empresa["nota_valor"], "•", 1.6)
    if cfg.get("validade_dias"):
        marcador(f"Validade desta proposta: {cfg['validade_dias']} dias corridos.", "•", 1.6)

    par("PRAZO ENTREGA:", True, antes=18, depois=2, manter=True)
    par(f"{cfg['prazo_dias']} Dias corridos", depois=8)
    par("PAGAMENTO :", True, depois=2, manter=True)
    acumulado = 0.0
    for parc in cfg.get("pagamento") or empresa.get("pagamento_padrao", []):
        texto, valor = _texto_parcela(parc, total, acumulado, cfg_v.get("mostrar_valor_parcelas", False))
        acumulado += valor
        marcador(texto, "o", 0.6, justificar=False)

    # ----- responsabilidades e assinatura -----
    resp = empresa.get("responsabilidades", {})
    quebra()
    par("RESPONSABILIDADES", True, sublinhado=True, alinhar=WD_ALIGN_PARAGRAPH.CENTER, depois=8, manter=True)
    for chave, titulo in (("contratado", "Contratado:"), ("contratante", "Contratante:")):
        if resp.get(chave):
            par(titulo, True, depois=2, manter=True)
            for t in resp[chave]:
                marcador(t, "●", 0.3, justificar=False)
    par("Atenciosamente,", antes=14, depois=14, manter=True)
    r = empresa.get("responsavel", {})
    par(r.get("nome", ""), True, depois=0, manter=True)
    par(r.get("telefone", ""), depois=0, manter=True)
    par(r.get("email", ""), depois=0)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destino)
    return destino


def converter_pdf(docx: Path) -> Path | None:
    """Converte para PDF com o LibreOffice, se instalado. Devolve None se não for possível."""
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(docx.parent), str(docx)],
                   check=True, capture_output=True, timeout=180)
    pdf = docx.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def nome_arquivo(cfg: dict, empresa: dict) -> str:
    cod = codigo_proposta(cfg, empresa).replace("/", "-")
    sufixo = " (RASCUNHO)" if cfg["status"] == "rascunho" else ""
    return f"{cod} - {cfg['cliente']['nome']} - PROPOSTA REV {int(cfg.get('revisao', 0)):02d}{sufixo}"
