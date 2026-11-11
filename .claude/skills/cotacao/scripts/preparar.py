"""Prepara um projeto para leitura pelos agentes: renderiza cada prancha em alta resolução,
gera recortes ampliados (2 linhas x 3 colunas, com sobreposição) e extrai o texto vetorial.

Uso:  python3 -I preparar.py <arquivo.pdf | pasta> <pasta_de_saida>

Saída (em <pasta_de_saida>):
  <arq>_pN_full.png            prancha inteira
  <arq>_pN_r{1,2}c{1,2,3}.png  recortes ampliados (para cotas, legendas e símbolos pequenos)
  texto.txt                    texto extraído de todas as páginas
"""
import shutil
import sys
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

IMAGENS = {".png", ".jpg", ".jpeg", ".webp"}


def processar_pdf(pdf_path: Path, saida: Path, texto) -> int:
    base = pdf_path.stem[:40].replace(" ", "_")
    doc = pdfium.PdfDocument(str(pdf_path))
    for i in range(len(doc)):
        im = doc[i].render(scale=4).to_pil().convert("RGB")
        w, h = im.size
        im.resize((w // 2, h // 2)).save(saida / f"{base}_p{i + 1}_full.png")
        cw, ch = int(w / 3 * 1.15), int(h / 2 * 1.15)
        for r in range(2):
            for c in range(3):
                x, y = min(int(c * w / 3), w - cw), min(int(r * h / 2), h - ch)
                im.crop((x, y, x + cw, y + ch)).save(saida / f"{base}_p{i + 1}_r{r + 1}c{c + 1}.png")
    with pdfplumber.open(pdf_path) as pdf:
        for i, pg in enumerate(pdf.pages, 1):
            texto.write(f"\n===== {pdf_path.name} - PÁGINA {i} =====\n{pg.extract_text() or ''}\n")
    return len(doc)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    origem, saida = Path(sys.argv[1]), Path(sys.argv[2])
    saida.mkdir(parents=True, exist_ok=True)
    arquivos = sorted(origem.rglob("*")) if origem.is_dir() else [origem]
    total = 0
    with open(saida / "texto.txt", "w", encoding="utf-8") as texto:
        for a in arquivos:
            if a.suffix.lower() == ".pdf":
                total += processar_pdf(a, saida, texto)
            elif a.suffix.lower() in IMAGENS:
                shutil.copy(a, saida / a.name)
                total += 1
            elif a.suffix.lower() in {".txt", ".md", ".csv"}:
                texto.write(f"\n===== {a.name} =====\n{a.read_text(encoding='utf-8', errors='replace')}\n")
    print(f"{total} página(s)/imagem(ns) preparadas em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
