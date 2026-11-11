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
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐
 │ 1. Extrator  │─▶│ 2. Validador │─▶│ 3. Revisor   │─▶│ 4. Pesquisa de     │─▶ planilha .xlsx
 │ lê o projeto │  │ refaz contas,│  │ final: decide│  │ preços: lojas, em  │
 │ e lista tudo │  │ corrige e    │  │ divergências │  │ paralelo, só dos   │
 │              │  │ completa     │  │ e fecha      │  │ materiais          │
 └──────────────┘  └──────────────┘  └──────────────┘  └────────────────────┘
```

As etapas 1 a 3 rodam pela API (`python -m cotaai processar`) ou pela skill `/cotacao`. A etapa 4
(preços) roda pela skill `/cotacao`, com o agente `pesquisador-de-precos`.

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
adotadas, itens removidos na validação e materiais sem preço encontrado.

Com a etapa de preços, a planilha ganha mais informação:

- **Materiais:** preço mínimo, médio e máximo por unidade do orçamento, loja do menor preço,
  lojas pesquisadas, total estimado (no menor preço e no preço médio) e a situação do preço
  (encontrado, parcial, não encontrado).
- **Preços (detalhe):** uma linha por cotação, com loja, produto, preço, conversão de embalagem,
  equivalência, estoque, data e **link da página**. A coluna "Considerar" (Sim/Não) decide o que
  entra nos cálculos; ao mudar, os preços e os totais da aba Materiais se atualizam.
- **Lojas consultadas:** em quais lojas a busca foi feita e **como** (página do produto aberta ou
  só resultado de busca), quantos itens cada loja cobriu e quais não deram resultado.

Cotações "sem estoque" e alternativas "aproximadas" aparecem no detalhe, mas não entram na média.
Os totais somam só os materiais com preço encontrado, então o valor real da obra é maior.

Cores das linhas: **amarelo** = corrigido, **azul** = adicionado pelo validador,
**verde** = adicionado na revisão final.

> ⚠️ Os quantitativos são gerados por IA. Use a memória de cálculo para conferir os
> itens mais caros antes de fechar contratos.

## Skills do Claude Code

O repositório traz duas skills em `.claude/skills/`. Abra o Claude Code na pasta do projeto e
digite o comando (sem acento: `/cotacao`):

| Comando | O que faz |
|---|---|
| `/cotacao [projeto]` | Roda os agentes (extrator, validador, revisor final e **pesquisador de preços**) sobre o projeto e entrega a planilha Excel com Materiais (com preços de mercado), Serviços, detalhe dos preços, lojas consultadas e as pendências a confirmar antes de cotar. Não precisa de chave da API: usa o seu plano do Claude. |
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

## Pesquisa de preços: lojas e limites

As lojas pesquisadas ficam em `.claude/skills/cotacao/lojas.json` (Leroy Merlin, Telhanorte,
Amoedo, Fluzão, Os Carvalhos, C&C, Obramax e, só como complemento, Magalu e Mercado Livre).
Edite o arquivo para incluir lojas, corrigir domínios ou mudar a prioridade.

O agente só registra preço que apareceu no texto da busca ou da página, com o link. O que ele
**não** consegue fazer, e a planilha informa na aba "Lojas consultadas":

- **Abrir páginas de produto** depende de a rede do ambiente permitir os sites das lojas. Sem isso,
  o preço vem do resultado de busca, que pode estar desatualizado (a planilha marca "Resultado de
  busca" e a data de validade, quando o site informa).
- **Lojas sem catálogo online** (comum em redes locais) não têm preço a pesquisar: aparecem como
  "cotar por telefone ou WhatsApp".
- **Preço depende de região e estoque.** Sites mostram o preço de referência de uma praça; confirme
  com a loja antes de fechar.

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
