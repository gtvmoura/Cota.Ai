"""Orquestra as três etapas e grava os resultados.

Saída em <pasta_saida>/<projeto>/:
  etapa1_extrator.json, etapa2_validador.json, etapa3_final.json
  <projeto> - levantamento.xlsx
Se uma etapa falhar, rodar de novo retoma da etapa que faltou (desde que os
arquivos do projeto não tenham mudado).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import agentes
from .planilha import gerar_planilha
from .projeto import blocos_conteudo, carregar_projeto

ETAPAS = ("etapa1_extrator.json", "etapa2_validador.json", "etapa3_final.json")
ARQ_HASH = ".hash_projeto"


def _ler(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _gravar(p: Path, dados: dict) -> None:
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def processar(caminho_projeto: Path, pasta_saida: Path, client=None) -> Path:
    projeto = carregar_projeto(caminho_projeto)
    saida = Path(pasta_saida) / projeto.nome
    saida.mkdir(parents=True, exist_ok=True)

    hash_atual = projeto.hash()
    arq_hash = saida / ARQ_HASH
    if not arq_hash.exists() or arq_hash.read_text().strip() != hash_atual:
        for nome in ETAPAS:  # projeto mudou: refaz tudo
            (saida / nome).unlink(missing_ok=True)
        arq_hash.write_text(hash_atual)

    print(f"\n=== Projeto: {projeto.nome} ({len(projeto.arquivos)} arquivo(s)) ===")
    for ign in projeto.ignorados:
        print(f"  aviso: ignorado (formato não suportado): {ign.name}")

    client = client or agentes.criar_cliente()
    blocos = blocos_conteudo(projeto)
    p1, p2, p3 = (saida / n for n in ETAPAS)

    etapa1 = _ler(p1)
    if etapa1 is None:
        etapa1 = agentes.extrair(client, blocos)
        _gravar(p1, etapa1)
    else:
        print("[1/3 extrator] já feito — reaproveitando")

    etapa2 = _ler(p2)
    if etapa2 is None:
        etapa2 = agentes.validar(client, blocos, etapa1)
        _gravar(p2, etapa2)
    else:
        print("[2/3 validador] já feito — reaproveitando")

    final = _ler(p3)
    if final is None:
        final = agentes.revisar(client, blocos, etapa1, etapa2)
        _gravar(p3, final)
    else:
        print("[3/3 revisor final] já feito — reaproveitando")

    xlsx = gerar_planilha(final, saida / f"{projeto.nome} - levantamento.xlsx", projeto.nome)
    print(
        f"Planilha: {xlsx}  ({len(final['materiais'])} materiais, "
        f"{len(final['servicos'])} serviços, {len(final['pendencias'])} pendências)"
    )
    return xlsx


def projetos_pendentes(pasta_entrada: Path, pasta_saida: Path) -> list[Path]:
    """Itens de pasta_entrada (arquivo solto ou subpasta) sem planilha atualizada."""
    pendentes = []
    for item in sorted(Path(pasta_entrada).iterdir()):
        if item.name.startswith("."):
            continue
        try:
            projeto = carregar_projeto(item)
        except (ValueError, FileNotFoundError) as e:
            print(f"aviso: {item.name}: {e}")
            continue
        saida = Path(pasta_saida) / projeto.nome
        xlsx = saida / f"{projeto.nome} - levantamento.xlsx"
        arq_hash = saida / ARQ_HASH
        if not (xlsx.exists() and arq_hash.exists() and arq_hash.read_text().strip() == projeto.hash()):
            pendentes.append(item)
    return pendentes
