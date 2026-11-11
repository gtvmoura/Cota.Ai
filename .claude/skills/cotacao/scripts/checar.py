"""Uso: python3 checar.py <arquivo.json>  — confere o JSON de uma etapa contra o esquema do Cota.Ai."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # raiz do repositório
from cotaai.schema import LEVANTAMENTO_SCHEMA
def chk(s, d, p="raiz"):
    t = s["type"]
    if t == "object":
        assert isinstance(d, dict), f"{p}: esperado objeto"
        falt = set(s["required"]) - set(d); extra = set(d) - set(s["required"])
        assert not falt and not extra, f"{p}: faltando {falt} / sobrando {extra}"
        for k, sub in s["properties"].items(): chk(sub, d[k], f"{p}.{k}")
    elif t == "array":
        assert isinstance(d, list), f"{p}: esperado lista"
        for i, it in enumerate(d): chk(s["items"], it, f"{p}[{i}]")
    elif t == "string":
        assert isinstance(d, str), f"{p}: esperado texto"
        if "enum" in s: assert d in s["enum"], f"{p}: '{d}' fora de {s['enum']}"
    elif t == "number": assert isinstance(d, (int, float)) and not isinstance(d, bool), f"{p}: esperado número"
    elif t == "boolean": assert isinstance(d, bool), f"{p}: esperado true/false"
d = json.load(open(sys.argv[1], encoding="utf-8")); chk(LEVANTAMENTO_SCHEMA, d)
ids = [x["id"] for x in d["materiais"] + d["servicos"]]
assert len(ids) == len(set(ids)), "ids duplicados"
print(f"OK: {len(d['materiais'])} materiais, {len(d['servicos'])} serviços, {len(d['pendencias'])} pendências")
