"""Linha de comando do Cota.Ai.

  python -m cotaai processar projetos/casa-silva           # um projeto (arquivo ou pasta)
  python -m cotaai novos                                    # todos os projetos ainda não processados
  python -m cotaai monitorar                                # fica de olho na pasta e processa sozinho
  python -m cotaai planilha cotacoes/casa-silva/etapa3_final.json   # regera o Excel (usa precos.json se existir)
  python -m cotaai precos-mesclar cotacoes/casa-silva/precos_lote*.json --final cotacoes/casa-silva/etapa3_final.json
  python -m cotaai precos-checar cotacoes/casa-silva/precos.json --final cotacoes/casa-silva/etapa3_final.json
  python -m cotaai proposta-init cotacoes/casa-silva        # cria proposta/proposta.json e o rascunho do conteúdo
  python -m cotaai proposta cotacoes/casa-silva --pdf       # gera a proposta comercial (DOCX e PDF)
  python -m cotaai proposta cotacoes/casa-silva --verificar # só mostra totais e o que falta preencher
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ENTRADA = Path("projetos")
SAIDA = Path("cotacoes")


def _rodar(caminhos: list[Path], saida: Path) -> int:
    from . import agentes
    from .pipeline import processar

    falhas = 0
    client = agentes.criar_cliente()
    for caminho in caminhos:
        try:
            processar(caminho, saida, client)
        except Exception as e:  # segue para o próximo projeto
            falhas += 1
            print(f"ERRO em {caminho.name}: {agentes.tratar_erro_api(e)}", file=sys.stderr)
    return 1 if falhas else 0


def _carregar_empresa(caminho: Path) -> dict:
    exemplo = Path(__file__).resolve().parents[1] / ".claude/skills/proposta/assets/empresa.exemplo.json"
    if not caminho.exists():
        print(f"AVISO: {caminho} não existe; usando dados de EXEMPLO. Copie {exemplo.name} para {caminho} e preencha.",
              file=sys.stderr)
        caminho = exemplo
    return json.loads(caminho.read_text(encoding="utf-8"))


def _proposta(a) -> int:
    import datetime as dt

    from . import proposta as PR

    pasta = a.pasta
    final_p = pasta / "etapa3_final.json"
    if not final_p.exists():
        print(f"Falta {final_p}: rode a /cotacao antes.", file=sys.stderr)
        return 1
    final = json.loads(final_p.read_text(encoding="utf-8"))
    empresa = _carregar_empresa(a.empresa)
    pp = pasta / "proposta"
    pp.mkdir(exist_ok=True)
    cfg_p, cont_p = pp / "proposta.json", pp / "proposta_conteudo.json"

    if a.cmd == "proposta-init":
        if not cfg_p.exists():
            cfg = {
                "status": "rascunho", "validado_por": "", "numero": None, "ano": dt.date.today().year,
                "revisao": 0, "data": dt.date.today().isoformat(),
                "cliente": {"nome": "(a preencher)", "aos_cuidados": "", "telefone": "", "email": ""},
                "referencia": "Orçamento Serviço", "tipo_obra": "", "projeto_referencia": "",
                "prazo_dias": None, "validade_dias": None,
                "pagamento": empresa.get("pagamento_padrao", []),
                "valores": {"modo": "global", "rotulo": "", "acrescimos": [{"descricao": "BDI", "percentual": 0}],
                            "valor_final_manual": None, "mostrar_valor_parcelas": False,
                            "permitir_itens_sem_valor": False},
            }
            cfg_p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Criado {cfg_p}")
        else:
            print(f"Mantido {cfg_p}")
        if not cont_p.exists():
            cont_p.write_text(json.dumps(PR.memorial_automatico(final, empresa), ensure_ascii=False, indent=2),
                              encoding="utf-8")
            print(f"Criado {cont_p} (rascunho automático: peça ao agente redator para refinar)")
        return 0

    if not cfg_p.exists():
        print(f"Falta {cfg_p}: rode 'proposta-init' primeiro.", file=sys.stderr)
        return 1
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    conteudo = (json.loads(cont_p.read_text(encoding="utf-8")) if cont_p.exists()
                else PR.memorial_automatico(final, empresa))
    planilha = a.planilha or next(iter(sorted(pasta.glob("*levantamento*.xlsx"))), None)
    if not planilha:
        print("Falta a planilha validada (*levantamento*.xlsx).", file=sys.stderr)
        return 1
    precos_p = pasta / "precos.json"
    precos = json.loads(precos_p.read_text(encoding="utf-8")) if precos_p.exists() else None

    rascunho = cfg.get("status") != "final"
    problemas = PR.validar_proposta(cfg)
    if cfg.get("status") == "final" and not cfg.get("validado_por"):
        problemas.append("status 'final' exige 'validado_por' (quem validou quantidades e valores)")
    problemas += PR.validar_conteudo(conteudo)
    calc = PR.calcular(PR.ler_valores(planilha, precos), cfg.get("valores", {}))
    if calc["sem_preco"]:
        problemas.append(f"{len(calc['sem_preco'])} material(is) sem preço adotado (ficam fora do total)")
    if calc["sem_valor"]:
        problemas.append(f"{len(calc['sem_valor'])} serviço(s) sem valor unitário (ficam fora do total)")
    if calc["total"] <= 0:
        problemas.append("o total da proposta é zero: preencha os valores na planilha")

    print(f"Planilha: {planilha.name}")
    print(f"  Materiais {PR.brl(calc['materiais'])} | Serviços {PR.brl(calc['servicos'])} | "
          f"Subtotal {PR.brl(calc['subtotal'])}")
    for ar, v in sorted(calc["servicos_por_area"].items()):
        print(f"    serviços: {ar}: {PR.brl(v)}")
    for ac in calc["acrescimos"]:
        print(f"  {ac['descricao']} ({ac['percentual']}%): {PR.brl(ac['valor'])}")
    print(f"  TOTAL {PR.brl(calc['total'])}" + ("  (valor final manual)" if calc["manual"] else ""))
    for pr in problemas:
        print(("PENDÊNCIA: " if rascunho else "ERRO: ") + pr)
    if a.verificar:
        return 0
    permitido = cfg.get("valores", {}).get("permitir_itens_sem_valor", False)
    graves = [p for p in problemas if not (permitido and "fora do total" in p)]
    if not rascunho and graves:
        print("Proposta FINAL não gerada: resolva os erros acima (ou use status 'rascunho').", file=sys.stderr)
        return 1
    if rascunho:  # rascunho tolera campos em branco, mas deixa visível
        cfg.setdefault("tipo_obra", "")
        cfg["tipo_obra"] = cfg["tipo_obra"] or "(tipo de obra)"
        cfg["prazo_dias"] = cfg.get("prazo_dias") or "(prazo)"
        cfg["numero"] = cfg.get("numero") or 0
        cfg["cliente"]["nome"] = cfg["cliente"].get("nome") or "(a preencher)"
    nome = PR.nome_arquivo(cfg, empresa)
    docx = PR.gerar_docx(empresa, cfg, conteudo, calc, pp / f"{nome}.docx", raiz=Path.cwd())
    print(f"Gerado {docx}")
    if a.pdf:
        pdf = PR.converter_pdf(docx)
        print(f"Gerado {pdf}" if pdf else "PDF não gerado: LibreOffice não encontrado (abra o DOCX e exporte).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cotaai", description="Levantamento de materiais e serviços com IA")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("processar", help="processa um projeto (arquivo ou pasta)")
    p.add_argument("caminho", type=Path, nargs="+")
    p.add_argument("--saida", type=Path, default=SAIDA)

    p = sub.add_parser("novos", help="processa os projetos de --entrada sem planilha atualizada")
    p.add_argument("--entrada", type=Path, default=ENTRADA)
    p.add_argument("--saida", type=Path, default=SAIDA)

    p = sub.add_parser("monitorar", help="verifica a pasta de entrada periodicamente")
    p.add_argument("--entrada", type=Path, default=ENTRADA)
    p.add_argument("--saida", type=Path, default=SAIDA)
    p.add_argument("--intervalo", type=int, default=60, help="segundos entre verificações")

    p = sub.add_parser("planilha", help="regera o Excel a partir de um JSON de etapa")
    p.add_argument("json", type=Path)
    p.add_argument("--destino", type=Path)
    p.add_argument("--precos", type=Path, help="JSON de preços (padrão: precos.json ao lado do JSON da etapa)")
    p.add_argument("--sem-precos", action="store_true", help="gera a planilha sem as colunas de preço")

    p = sub.add_parser("precos-mesclar", help="junta os lotes de pesquisa de preços em precos.json")
    p.add_argument("lotes", type=Path, nargs="+")
    p.add_argument("--saida", type=Path)
    p.add_argument("--final", type=Path, help="etapa3_final.json, para conferir os ids dos materiais")

    p = sub.add_parser("precos-checar", help="confere um JSON de preços")
    p.add_argument("json", type=Path)
    p.add_argument("--final", type=Path, help="etapa3_final.json, para conferir os ids dos materiais")
    p.add_argument("--lote", type=Path, help="lote_NN_materiais.json: confere só os ids desse lote")

    p = sub.add_parser("proposta-init", help="cria a configuração e o rascunho de conteúdo da proposta comercial")
    p.add_argument("pasta", type=Path, help="pasta da obra (com etapa3_final.json)")
    p.add_argument("--empresa", type=Path, default=Path("empresa/empresa.json"))

    p = sub.add_parser("proposta", help="gera a proposta comercial a partir da planilha validada")
    p.add_argument("pasta", type=Path, help="pasta da obra (com etapa3_final.json e a planilha)")
    p.add_argument("--planilha", type=Path, help="planilha validada (padrão: *levantamento*.xlsx da pasta)")
    p.add_argument("--empresa", type=Path, default=Path("empresa/empresa.json"))
    p.add_argument("--pdf", action="store_true", help="também gera o PDF (precisa do LibreOffice)")
    p.add_argument("--verificar", action="store_true", help="só mostra totais e pendências, sem gerar arquivos")

    a = ap.parse_args(argv)

    if a.cmd == "processar":
        return _rodar(a.caminho, a.saida)

    if a.cmd == "novos":
        from .pipeline import projetos_pendentes
        pendentes = projetos_pendentes(a.entrada, a.saida)
        if not pendentes:
            print("Nenhum projeto novo ou alterado.")
            return 0
        return _rodar(pendentes, a.saida)

    if a.cmd == "monitorar":
        from .pipeline import projetos_pendentes
        print(f"Monitorando '{a.entrada}/' a cada {a.intervalo}s. Ctrl+C para sair.")
        ultimo_tamanho: dict[Path, int] = {}
        while True:
            pendentes = projetos_pendentes(a.entrada, a.saida)
            # Só processa quando o upload terminou (tamanho estável entre duas verificações).
            prontos = []
            for item in pendentes:
                tam = sum(f.stat().st_size for f in ([item] if item.is_file() else item.rglob("*")) if f.is_file())
                if ultimo_tamanho.get(item) == tam:
                    prontos.append(item)
                ultimo_tamanho[item] = tam
            if prontos:
                _rodar(prontos, a.saida)
            time.sleep(a.intervalo)

    if a.cmd in ("proposta-init", "proposta"):
        return _proposta(a)

    if a.cmd == "planilha":
        from .planilha import gerar_planilha
        dados = json.loads(a.json.read_text(encoding="utf-8"))
        nome = a.json.parent.name
        destino = a.destino or a.json.with_name(f"{nome} - levantamento.xlsx")
        arq_precos = a.precos or a.json.with_name("precos.json")
        precos = None
        if not a.sem_precos and arq_precos.exists():
            precos = json.loads(arq_precos.read_text(encoding="utf-8"))
            print(f"Usando preços de {arq_precos}")
        print(gerar_planilha(dados, destino, nome, precos))
        return 0

    if a.cmd in ("precos-mesclar", "precos-checar"):
        from . import precos as P
        ids = None
        if a.final:
            fin = json.loads(a.final.read_text(encoding="utf-8"))
            ids = {m["id"] for m in fin["materiais"]}
        if getattr(a, "lote", None):
            ids = {m["id"] for m in json.loads(a.lote.read_text(encoding="utf-8"))["materiais"]}
        if a.cmd == "precos-mesclar":
            lotes = [json.loads(p.read_text(encoding="utf-8")) for p in a.lotes]
            for p, lote in zip(a.lotes, lotes):
                probs = P.validar(lote)
                if probs:
                    print(f"{p.name}: " + "; ".join(probs[:5]), file=sys.stderr)
                    return 1
            dados = P.mesclar(lotes)
            saida = a.saida or a.lotes[0].with_name("precos.json")
            saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{saida}: {len(dados['itens'])} itens, {len(dados['lojas'])} lojas")
            a.json = saida
        dados = json.loads(a.json.read_text(encoding="utf-8"))
        probs = P.validar(dados, ids)
        if probs:
            print("PROBLEMAS:\n- " + "\n- ".join(probs), file=sys.stderr)
            return 1
        for al in P.alertas(dados):
            print("AVISO preço fora do padrão:", al)
        enc = sum(1 for i in dados["itens"] if i["status"] in ("encontrado", "parcial"))
        print(f"OK: {len(dados['itens'])} itens ({enc} com preço), {len(dados['lojas'])} lojas")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
