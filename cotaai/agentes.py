"""Chamadas ao Claude para as três etapas (extrator, validador, revisor final)."""

from __future__ import annotations

import json
import os
import sys
import time

import anthropic

from . import prompts
from .schema import LEVANTAMENTO_SCHEMA

MODELO = os.environ.get("COTAAI_MODELO", "claude-opus-5-5")
# Esforço de raciocínio: low | medium | high | xhigh | max.
# Levantamento de quantitativos é trabalho minucioso — "high" é um bom ponto de partida.
ESFORCO = os.environ.get("COTAAI_ESFORCO", "high")
MAX_TOKENS = int(os.environ.get("COTAAI_MAX_TOKENS", "64000"))


class ErroAgente(RuntimeError):
    pass


def _chamar(client: anthropic.Anthropic, blocos_projeto: list[dict], instrucao: str, etapa: str) -> dict:
    """Envia projeto + instrução e devolve o JSON validado pelo esquema."""
    inicio = time.time()
    print(f"[{etapa}] enviando para {MODELO} (esforço {ESFORCO})...", flush=True)

    # O fallback no servidor re-executa a requisição em outro modelo caso o
    # classificador de segurança recuse (raro neste uso, mas evita perder a etapa).
    with client.beta.messages.stream(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        system=prompts.SYSTEM,
        thinking={"type": "adaptive"},
        output_config={
            "effort": ESFORCO,
            "format": {"type": "json_schema", "schema": LEVANTAMENTO_SCHEMA},
        },
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{
            "role": "user",
            "content": [*blocos_projeto, {"type": "text", "text": instrucao}],
        }],
    ) as stream:
        caracteres = 0
        proximo_aviso = 5000
        for evento in stream:
            if evento.type == "content_block_delta" and evento.delta.type == "text_delta":
                caracteres += len(evento.delta.text)
                if caracteres >= proximo_aviso:
                    print(f"[{etapa}] ... {caracteres:,} caracteres gerados", flush=True)
                    proximo_aviso += 5000
        resposta = stream.get_final_message()

    uso = resposta.usage
    print(
        f"[{etapa}] concluída em {time.time() - inicio:.0f}s — tokens: entrada {uso.input_tokens:,}, "
        f"cache lido {uso.cache_read_input_tokens or 0:,}, cache gravado "
        f"{uso.cache_creation_input_tokens or 0:,}, saída {uso.output_tokens:,}",
        flush=True,
    )

    if resposta.stop_reason == "refusal":
        detalhe = resposta.stop_details.explanation if resposta.stop_details else ""
        raise ErroAgente(f"[{etapa}] o modelo recusou a solicitação. {detalhe}")
    if resposta.stop_reason == "max_tokens":
        raise ErroAgente(
            f"[{etapa}] a resposta passou do limite de {MAX_TOKENS} tokens. Aumente "
            "COTAAI_MAX_TOKENS (máx. 128000) ou divida o projeto por disciplina."
        )

    texto = next((b.text for b in resposta.content if b.type == "text"), None)
    if not texto:
        raise ErroAgente(f"[{etapa}] resposta sem conteúdo (stop_reason={resposta.stop_reason}).")
    return json.loads(texto)


def criar_cliente() -> anthropic.Anthropic:
    # Lê ANTHROPIC_API_KEY (ou um perfil do `ant auth login`) do ambiente.
    # Timeout longo: projetos grandes em esforço alto podem levar vários minutos por etapa.
    return anthropic.Anthropic(timeout=60 * 30, max_retries=3)


def extrair(client, blocos_projeto) -> dict:
    return _chamar(client, blocos_projeto, prompts.instrucao_extrator(), "1/3 extrator")


def validar(client, blocos_projeto, etapa1: dict) -> dict:
    instrucao = prompts.instrucao_validador(json.dumps(etapa1, ensure_ascii=False, indent=1))
    return _chamar(client, blocos_projeto, instrucao, "2/3 validador")


def revisar(client, blocos_projeto, etapa1: dict, etapa2: dict) -> dict:
    instrucao = prompts.instrucao_revisor(
        json.dumps(etapa1, ensure_ascii=False, indent=1),
        json.dumps(etapa2, ensure_ascii=False, indent=1),
    )
    return _chamar(client, blocos_projeto, instrucao, "3/3 revisor final")


def tratar_erro_api(e: Exception) -> str:
    if isinstance(e, anthropic.AuthenticationError):
        return "Chave da API inválida ou ausente. Defina ANTHROPIC_API_KEY."
    if isinstance(e, anthropic.RateLimitError):
        return "Limite de uso da API atingido. Tente novamente em alguns minutos."
    if isinstance(e, anthropic.BadRequestError):
        return f"Requisição rejeitada pela API: {e.message}"
    if isinstance(e, anthropic.APIStatusError):
        return f"Erro da API ({e.status_code}): {e.message}"
    if isinstance(e, anthropic.APIConnectionError):
        return "Falha de conexão com a API. Verifique a internet."
    return str(e)


if __name__ == "__main__":  # pragma: no cover
    sys.exit("Use: python -m cotaai --help")
