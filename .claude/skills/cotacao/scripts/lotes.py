"""Divide os materiais de etapa3_final.json em lotes para os agentes de preço.

Uso:  python3 lotes.py <etapa3_final.json> <pasta_de_saida> [--tamanho 25]

Grava lote_01_materiais.json, lote_02_materiais.json... Os materiais da mesma etapa da obra ficam
juntos (cimento com cimento, elétrica com elétrica), o que ajuda o agente a reaproveitar buscas.
"""
import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("final", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--tamanho", type=int, default=25)
    a = ap.parse_args()

    dados = json.loads(a.final.read_text(encoding="utf-8"))
    mats = sorted(dados["materiais"], key=lambda m: (m["etapa_obra"], m["id"]))
    a.saida.mkdir(parents=True, exist_ok=True)
    n = (len(mats) + a.tamanho - 1) // a.tamanho
    # tamanhos parecidos entre os lotes
    base, extra = divmod(len(mats), n)
    i = 0
    for k in range(1, n + 1):
        qtd = base + (1 if k <= extra else 0)
        lote = [
            {
                "id": m["id"], "etapa_obra": m["etapa_obra"], "descricao": m["descricao"],
                "especificacao": m["especificacao"], "especificado_no_projeto": m["especificado_no_projeto"],
                "unidade": m["unidade"], "observacoes": m["observacoes"],
            }
            for m in mats[i:i + qtd]
        ]
        i += qtd
        arq = a.saida / f"lote_{k:02d}_materiais.json"
        arq.write_text(json.dumps({"lote": k, "total_lotes": n, "materiais": lote}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"{arq.name}: {len(lote)} materiais ({lote[0]['etapa_obra']} ... {lote[-1]['etapa_obra']})")


if __name__ == "__main__":
    main()
