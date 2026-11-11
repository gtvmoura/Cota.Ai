"""Etapa 4: preços de mercado. Validação, junção de lotes e estatísticas das pesquisas de preço.

Cada agente pesquisador recebe um lote de materiais e grava um JSON no formato PRECOS_SCHEMA.
Este módulo confere os arquivos, junta os lotes e calcula o resumo por item.
"""

from __future__ import annotations

import json
import statistics
from collections import OrderedDict

from .schema import PRECOS_SCHEMA, validar_schema

ROTULO_ACESSO = {
    "pagina_aberta": "Página do produto aberta",
    "somente_busca": "Somente resultado de busca (preço pode estar desatualizado)",
    "catalogo_sem_preco": "Site com catálogo, mas sem preços públicos: cotar por telefone ou WhatsApp",
    "sem_acesso": "Sem acesso ao site (não consultada)",
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


def _status(cotacoes: list[dict], anterior: str) -> str:
    """Recalcula o status do item: encontrado = 2 ou mais lojas com cotação exata/similar."""
    validas = [c for c in cotacoes if c["equivalencia"] != "aproximada"]
    if not cotacoes:
        return anterior if anterior == "nao_aplicavel" else "nao_encontrado"
    return "encontrado" if len({c["loja"] for c in validas}) >= 2 else "parcial"


def mesclar(lotes: list[dict]) -> dict:
    """Junta vários lotes (um por agente) em um único arquivo de preços.

    Se o mesmo material aparece em mais de um arquivo (pesquisa complementar numa loja), as
    cotações são somadas, as lojas pesquisadas unidas e o status recalculado.
    """
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
                # o acesso mais fraco prevalece (é o que o usuário precisa saber), mas só conta quem
                # de fato pesquisou a loja: um lote com 0 itens pesquisados não diz nada sobre ela
                ordem = ["pagina_aberta", "somente_busca", "catalogo_sem_preco", "sem_acesso", "sem_presenca_online"]
                if l["itens_pesquisados"] > 0 and (
                    atual["itens_pesquisados"] - l["itens_pesquisados"] == 0
                    or ordem.index(l["acesso"]) > ordem.index(atual["acesso"])
                ):
                    atual["acesso"] = l["acesso"]
                if l["observacao"] and l["observacao"] not in atual["observacao"]:
                    atual["observacao"] = (atual["observacao"] + " " + l["observacao"]).strip()
        for it in lote["itens"]:
            if it["id"] not in itens:
                itens[it["id"]] = json.loads(json.dumps(it))
                continue
            base = itens[it["id"]]
            existentes = {(c["loja"], c["fonte"]) for c in base["cotacoes"]}
            base["cotacoes"] += [c for c in it["cotacoes"] if (c["loja"], c["fonte"]) not in existentes]
            base["lojas_pesquisadas"] = list(dict.fromkeys(base["lojas_pesquisadas"] + it["lojas_pesquisadas"]))
            if it["observacao"] and it["observacao"] not in base["observacao"]:
                base["observacao"] = (base["observacao"] + " | " + it["observacao"]).strip(" |")
            base["status"] = _status(base["cotacoes"], base["status"])
    # uma loja que deu preço em algum lote não pode ficar como "sem acesso" ou "catálogo sem preço"
    for l in lojas.values():
        if l["itens_com_preco"] > 0 and l["acesso"] in ("sem_acesso", "catalogo_sem_preco", "sem_presenca_online"):
            l["acesso"] = "somente_busca"
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


def alertas(dados: dict, fator: float = 3.0) -> list[str]:
    """Cotações muito distantes das demais do mesmo item (>= `fator` vezes a mediana, ou o inverso).

    Só avalia itens com 3 ou mais cotações válidas. Serve para o usuário revisar: não remove nada.
    """
    saida = []
    for it in dados["itens"]:
        validas = [c for c in it["cotacoes"] if considerar(c)]
        if len(validas) < 3:
            continue
        med = statistics.median(c["preco_unitario"] for c in validas)
        for c in validas:
            r = c["preco_unitario"] / med
            if r >= fator or r <= 1 / fator:
                saida.append(f"{it['id']} {c['loja']}: R$ {c['preco_unitario']:.2f} contra mediana R$ {med:.2f}")
    return saida


def fora_do_padrao(item: dict, cotacao: dict, fator: float = 3.0) -> bool:
    validas = [c for c in item["cotacoes"] if considerar(c)]
    if len(validas) < 3 or not considerar(cotacao):
        return False
    med = statistics.median(c["preco_unitario"] for c in validas)
    r = cotacao["preco_unitario"] / med
    return r >= fator or r <= 1 / fator
