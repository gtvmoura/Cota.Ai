"""Carrega os arquivos de um projeto e monta os blocos de conteúdo para o Claude.

Um "projeto" pode ser um único arquivo ou uma pasta com vários arquivos
(ex.: arquitetônico.pdf + estrutural.pdf + memorial.pdf + fotos).
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

PDF = {".pdf"}
IMAGENS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
TEXTO = {".txt", ".md", ".csv"}
SUPORTADOS = PDF | set(IMAGENS) | TEXTO

# Limite da API para PDF: 32 MB por requisição (o base64 cresce ~33%).
LIMITE_BYTES_REQUISICAO = 32 * 1024 * 1024


@dataclass
class Projeto:
    nome: str
    arquivos: list[Path]
    ignorados: list[Path] = field(default_factory=list)

    def hash(self) -> str:
        h = hashlib.sha256()
        for arq in self.arquivos:
            h.update(arq.name.encode())
            h.update(arq.read_bytes())
        return h.hexdigest()


def carregar_projeto(caminho: Path) -> Projeto:
    caminho = Path(caminho)
    if caminho.is_dir():
        todos = sorted(p for p in caminho.rglob("*") if p.is_file() and not p.name.startswith("."))
        nome = caminho.name
    elif caminho.is_file():
        todos = [caminho]
        nome = caminho.stem
    else:
        raise FileNotFoundError(f"Projeto não encontrado: {caminho}")

    arquivos = [p for p in todos if p.suffix.lower() in SUPORTADOS]
    ignorados = [p for p in todos if p.suffix.lower() not in SUPORTADOS]
    if not arquivos:
        raise ValueError(
            f"Nenhum arquivo suportado em {caminho}. Aceitos: PDF, PNG/JPG/WEBP, TXT/MD/CSV. "
            "Arquivos DWG/RVT/IFC precisam ser exportados para PDF antes."
        )
    total = sum(p.stat().st_size for p in arquivos if p.suffix.lower() in PDF | set(IMAGENS))
    if total * 4 / 3 > LIMITE_BYTES_REQUISICAO:
        raise ValueError(
            f"O projeto '{nome}' tem {total / 1e6:.1f} MB em PDFs/imagens — acima do limite de "
            "32 MB por requisição. Divida-o em pastas por disciplina ou reduza a resolução dos PDFs."
        )
    return Projeto(nome=nome, arquivos=arquivos, ignorados=ignorados)


def _texto_pdf(caminho: Path) -> str:
    """Extrai o texto vetorial do PDF (cotas, legendas, quadros, carimbos).

    O Claude também "vê" cada página como imagem, mas em pranchas grandes (A0/A1)
    a imagem é reduzida e textos pequenos podem ficar ilegíveis — o texto
    extraído complementa isso.
    """
    try:
        import pdfplumber
    except ImportError:
        return ""
    partes = []
    with pdfplumber.open(caminho) as pdf:
        for i, pagina in enumerate(pdf.pages, start=1):
            texto = (pagina.extract_text() or "").strip()
            if texto:
                partes.append(f"--- página {i} ---\n{texto}")
    return "\n\n".join(partes)


def blocos_conteudo(projeto: Projeto) -> list[dict]:
    """Monta os blocos (documentos, imagens e texto) que representam o projeto."""
    blocos: list[dict] = [
        {"type": "text", "text": f"PROJETO: {projeto.nome}\nArquivos recebidos: "
         + ", ".join(p.name for p in projeto.arquivos)}
    ]
    textos_extraidos = []
    for arq in projeto.arquivos:
        ext = arq.suffix.lower()
        if ext in PDF:
            blocos.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(arq.read_bytes()).decode(),
                },
                "title": arq.name,
            })
            texto = _texto_pdf(arq)
            if texto:
                textos_extraidos.append(f"===== {arq.name} =====\n{texto}")
        elif ext in IMAGENS:
            blocos.append({"type": "text", "text": f"Imagem: {arq.name}"})
            blocos.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": IMAGENS[ext],
                    "data": base64.standard_b64encode(arq.read_bytes()).decode(),
                },
            })
        else:
            textos_extraidos.append(
                f"===== {arq.name} =====\n{arq.read_text(encoding='utf-8', errors='replace')}"
            )
    if textos_extraidos:
        blocos.append({
            "type": "text",
            "text": "TEXTO EXTRAÍDO DOS ARQUIVOS (use para ler cotas, legendas e quadros "
            "que fiquem pequenos nas imagens):\n\n" + "\n\n".join(textos_extraidos),
        })
    # Marca o fim do projeto para cache: as etapas 2 e 3 reaproveitam este prefixo.
    blocos[-1]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
    return blocos
