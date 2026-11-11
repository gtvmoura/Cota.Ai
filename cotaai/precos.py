"""Etapa 4: preços de mercado. Validação, junção de lotes e estatísticas das pesquisas de preço.

Cada agente pesquisador recebe um lote de materiais e grava um JSON no formato PRECOS_SCHEMA.
Este módulo confere os arquivos, junta os lotes e calcula o resumo por item.
"""

from __future__ import annotations

import statistics
from collections import OrderedDict

from .schema import PRECOS_SCHEMA, validar_schema

ROTULO_ACESSO = {
    "pagina_aberta": "Página do produto aberta",
    "somente_busca": "Somente resultado de busca (preço pode estar desatualizado)",
    "sem_acesso": "Sem acesso ao site",
    "sem_presenca_online": "Sem catálogo online encontrado: cotar por telefone ou WhatsApp",
}
ROTULO_STATUS = {
    "encontrado": "Encontrado",
    "parcial": "Parcial",
    "nao_encontrado": "Não encontrado",
    "nao_aplicavel": "Não se aplica",
}


def validar(dados: dict, ids_materiais: set[str] | None = None) -> list[str]:
    """Devolve a lista de problemas (vazia se o arquivo está correto)."""
    problemas: list[str] = []
    try:
        validar_schema(PRECOS_SCHEMA, dados)
    except ValueError as e:
        return [str(e)]
    vistos: set[str] = set()
    lojas = {l["loja"] for l in dados["lojas"]}
    for it in dados["itens"]:
        i = it["id"]
        if i in vistos:
            problemas.append(f"{i}: id repetido")
        vistos.add(i)
        if ids_materiais is not None and i not in ids_materiais:
            problemas.append(f"{i}: id não existe nos materiais")
        n = len(it["cotacoes"])
        if it["status"] in ("nao_encontrado", "nao_aplicavel") and n:
            problemas.append(f"{i}: status '{it['status']}' mas há {n} cotação(ões)")
        if it["status"] in ("encontrado", "parcial") and not n:
            problemas.append(f"{i}: status '{it['status']}' sem cotações")
        for c in it["cotacoes"]:
            if c["preco_embalagem"] <= 0 or c["preco_unitario"] <= 0:
                problemas.append(f"{i}/{c['loja']}: preço não positivo")
            if not c["fonte"].startswith("http"):
                problemas.append(f"{i}/{c['loja']}: cotação sem URL de fonte")
            if c["loja"] not in lojas:
                problemas.append(f"{i}: loja '{c['loja']}' não está em 'lojas'")
            if c["metodo"] == "busca" and not c["fonte"]:
                problemas.append(f"{i}/{c['loja']}: sem fonte")
    if ids_materiais is not None:
        faltam = sorted(ids_materiais - vistos)
        if faltam:
            problemas.append(f"{len(faltam)} material(is) sem registro de pesquisa: {', '.join(faltam[:12])}...")
    return problemas


def mesclar(lotes: list[dict]) -> dict:
    """Junta vários lotes (um por agente) em um único arquivo de preços."""
    if not lotes:
        raise ValueError("nenhum lote para mesclar")
    lojas: "OrderedDict[str, dict]" = OrderedDict()
    itens: dict[str, dict] = {}
    obs: list[str] = []
    for lote in lotes:
        for o in lote["observacoes_gerais"]:
            if o not in obs:
                obs.append(o)
        for l in lote["lojas"]:
            if l["loja"] not in lojas:
                lojas[l["loja"]] = dict(l)
            else:
                atual = lojas[l["loja"]]
                atual["itens_pesquisados"] += l["itens_pesquisados"]
                atual["itens_com_preco"] += l["itens_com_preco"]
                # o acesso mais fraco prevalece (é o que o usuário precisa saber)
                ordem = ["pagina_aberta", "somente_busca", "sem_acesso", "sem_presenca_online"]
                if ordem.index(l["acesso"]) > ordem.index(atual["acesso"]):
                    atual["acesso"] = l["acesso"]
                if l["observacao"] and l["observacao"] not in atual["observacao"]:
                    atual["observacao"] = (atual["observacao"] + " " + l["observacao"]).strip()
        for it in lote["itens"]:
            if it["id"] in itens:
                raise ValueError(f"{it['id']} aparece em mais de um lote")
            itens[it["id"]] = it
    return {
        "data_consulta": max(l["data_consulta"] for l in lotes),
        "regiao": lotes[0]["regiao"],
        "observacoes_gerais": obs,
        "lojas": list(lojas.values()),
        "itens": sorted(itens.values(), key=lambda x: x["id"]),
    }


def considerar(cotacao: dict) -> bool:
    """Cotação entra nas estatísticas? Fora: sem estoque e alternativa 'aproximada'."""
    return cotacao["disponibilidade"] != "sem estoque" and cotacao["equivalencia"] != "aproximada"


def resumo_item(item: dict) -> dict:
    """Mínimo, médio, máximo e loja do menor preço, considerando só as cotações válidas."""
    validas = [c for c in item["cotacoes"] if considerar(c)]
    if not validas:
        return {"n": 0, "min": None, "medio": None, "max": None, "mediana": None, "loja_min": ""}
    precos = [c["preco_unitario"] for c in validas]
    menor = min(validas, key=lambda c: c["preco_unitario"])
    return {
        "n": len(validas),
        "min": min(precos),
        "medio": sum(precos) / len(precos),
        "max": max(precos),
        "mediana": statistics.median(precos),
        "loja_min": menor["loja"],
    }
