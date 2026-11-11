# Cota.Ai

Levantamento automático de **materiais** e **serviços** a partir de projetos de
arquitetura e engenharia, para agilizar as cotações da construtora.

Você envia o projeto e recebe uma planilha Excel pronta para mandar a fornecedores
e empreiteiros.

## Como funciona

```
 projeto (PDF/imagens/memorial)
        │
        ▼
 ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
 │ 1. Extrator      │──▶│ 2. Validador     │──▶│ 3. Revisor final     │──▶ planilha .xlsx
 │ lê o projeto e   │   │ refaz as contas, │   │ decide divergências, │
 │ lista tudo       │   │ corrige, remove  │   │ procura o que faltou │
 │                  │   │ e adiciona itens │   │ e consolida          │
 └──────────────────┘   └──────────────────┘   └──────────────────────┘
```

As três etapas leem o **projeto original**, não só a lista da etapa anterior. Cada
uma devolve a lista completa num formato fixo (JSON com esquema), então não há
risco de a planilha "quebrar" por causa de texto fora do padrão.

A IA inclui o que está **especificado** no projeto e também o que **não está
desenhado, mas é necessário** (canteiro, formas, argamassas, impermeabilização,
eletrodutos, limpeza etc.). Esses itens aparecem marcados como
"Não (sugerido)".

## A planilha

**Aba Materiais:** item, etapa da obra, material, especificação, se está especificado
no projeto, unidade, quantidade líquida, % de perda, quantidade para compra
(fórmula), memória de cálculo, referência no projeto (prancha/página), observações
e o resultado da validação.

**Aba Serviços:** item, serviço, área de atuação (Alvenaria, Elétrica,
Hidrossanitária…), local de aplicação, escopo, se está especificado no projeto,
unidade, quantidade/área, valor unitário **em branco** (para cotar), memória de
cálculo, referência e validação.

**Aba Notas da IA:** pendências para confirmar com o cliente/projetista, premissas
adotadas e itens removidos na validação.

Cores das linhas: **amarelo** = corrigido, **azul** = adicionado pelo validador,
**verde** = adicionado na revisão final.

> ⚠️ Os quantitativos são gerados por IA. Use a memória de cálculo para conferir os
> itens mais caros antes de fechar contratos.

## Skills do Claude Code

O repositório traz duas skills em `.claude/skills/`. Abra o Claude Code na pasta do projeto e
digite o comando (sem acento: `/cotacao`):

| Comando | O que faz |
|---|---|
| `/cotacao [projeto]` | Roda os três agentes (extrator, validador, revisor final) sobre o projeto e entrega a planilha Excel com as abas Materiais e Serviços, mais as pendências a confirmar antes de cotar. Não precisa de chave da API: usa o seu plano do Claude. |
| `/projeto3d [projeto]` | Monta a visualização 3D da obra com as fases Antes, Obra (o que demolir e o que construir) e Depois (com mobiliário), paredes translúcidas conforme o ângulo, botões de orientação e bússola. Publica como página privada. |

Exemplo: anexe o PDF do projeto na conversa e digite `/cotacao`, depois `/projeto3d`.
Os dois comandos usam o mesmo projeto e guardam os resultados em `cotacoes/<obra>/`.

> **Projetos de clientes:** não envie projetos nem planilhas de clientes para um repositório
> público. Deixe `projetos/` e `cotacoes/` fora do git ou torne o repositório privado.

## Instalação

Requer Python 3.10+ e uma chave da API da Anthropic
(https://console.anthropic.com → API Keys).

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."      # Windows: set ANTHROPIC_API_KEY=sk-ant-...
```

## Uso

Coloque cada projeto em `projetos/`, como **um arquivo** ou **uma pasta**, com todas
as disciplinas da mesma obra:

```
projetos/
  casa-silva/
    arquitetonico.pdf
    estrutural.pdf
    eletrico.pdf
    memorial-descritivo.pdf
  reforma-loja.pdf
```

Formatos aceitos: **PDF**, **PNG/JPG/WEBP** e **TXT/MD/CSV**. Arquivos DWG, RVT ou IFC
precisam ser exportados para PDF antes, pois são ignorados.

```bash
python -m cotaai processar projetos/casa-silva    # processa um projeto
python -m cotaai novos                            # processa todos os novos ou alterados
python -m cotaai monitorar                        # fica rodando e processa sozinho a cada upload
```

O resultado fica em `cotacoes/<projeto>/`:

- `<projeto> - levantamento.xlsx`: a planilha final
- `etapa1_extrator.json`, `etapa2_validador.json`, `etapa3_final.json`: o histórico
  de cada etapa, para auditoria

Se uma etapa falhar (por exemplo, a internet cair), rodar de novo **continua de onde
parou**. Se o projeto mudar, as três etapas são refeitas.

## Automação: "subiu o projeto, gerou a planilha"

**Opção A: pasta monitorada (no computador do escritório).** Deixe
`python -m cotaai monitorar` rodando. A pasta `projetos/` pode estar dentro do
Google Drive, OneDrive ou Dropbox: quem enviar um projeto para ela recebe a planilha
em `cotacoes/` alguns minutos depois. O processamento só começa quando o upload
termina.

**Opção B: GitHub Actions (na nuvem, sem computador ligado).** O workflow
`.github/workflows/cotacao.yml` roda sempre que um arquivo é enviado para
`projetos/` neste repositório e salva a planilha de volta em `cotacoes/`.
Configure uma vez em *Settings → Secrets and variables → Actions → New repository
secret*, com o nome `ANTHROPIC_API_KEY`. Os arquivos podem ser enviados pelo próprio
site do GitHub (*Add file → Upload files*).

## Ajustes

Variáveis de ambiente opcionais:

| Variável | Padrão | Para quê |
|---|---|---|
| `COTAAI_MODELO` | `claude-opus-5-5` | modelo usado nas três etapas |
| `COTAAI_ESFORCO` | `high` | `medium` é mais barato e rápido; `xhigh`/`max` é mais minucioso |
| `COTAAI_MAX_TOKENS` | `64000` | aumente (até 128000) se um projeto muito grande estourar o limite |

Para mudar a forma como a IA pensa (as regras da construtora, a nomenclatura e o que
sempre incluir), edite `cotaai/prompts.py`. Para mudar as colunas da planilha, edite
`cotaai/planilha.py` e `cotaai/schema.py`.

**Custos:** o projeto é enviado com cache, então as etapas 2 e 3 pagam bem menos
pela leitura dele. O consumo de tokens de cada etapa aparece no terminal.

**Limites:** até 32 MB de PDFs/imagens por projeto e 600 páginas. Projetos maiores
devem ser divididos em pastas por disciplina.

## Testes

```bash
python -m pytest -q     # simula as três etapas sem chamar a API
```
