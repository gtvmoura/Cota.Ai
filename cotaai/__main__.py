"""Linha de comando do Cota.Ai.

  python -m cotaai processar projetos/casa-silva           # um projeto (arquivo ou pasta)
  python -m cotaai novos                                    # todos os projetos ainda não processados
  python -m cotaai monitorar                                # fica de olho na pasta e processa sozinho
  python -m cotaai planilha cotacoes/casa-silva/etapa3_final.json   # regera o Excel (usa precos.json se existir)
  python -m cotaai precos-mesclar cotacoes/casa-silva/precos_lote*.json --final cotacoes/casa-silva/etapa3_final.json
  python -m cotaai precos-checar cotacoes/casa-silva/precos.json --final cotacoes/casa-silva/etapa3_final.json
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
        enc = sum(1 for i in dados["itens"] if i["status"] in ("encontrado", "parcial"))
        print(f"OK: {len(dados['itens'])} itens ({enc} com preço), {len(dados['lojas'])} lojas")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
