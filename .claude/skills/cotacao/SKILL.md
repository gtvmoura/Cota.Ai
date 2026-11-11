---
name: cotacao
description: Levantamento de materiais e serviços para cotação a partir de um projeto de arquitetura ou engenharia (PDF, imagens, memorial), com pesquisa de preços de mercado dos materiais em lojas. Roda agentes especializados em sequência (extrator, validador, revisor final, pesquisador de preços) e entrega uma planilha Excel com Materiais, Serviços, detalhe dos preços e lojas consultadas. Use quando o usuário digitar /cotacao, anexar um projeto pedindo cotação, orçamento, levantamento de quantitativos, lista de materiais e serviços ou pesquisa de preços.
argument-hint: "[caminho do projeto: arquivo PDF ou pasta]"
allowed-tools: Bash, Read, Write, Agent, WebSearch, WebFetch
---

# /cotacao: do projeto à planilha com preços

Transforma um projeto em uma planilha pronta para cotar, em cinco passos:

```
 Projeto ─▶ 1 Extrator ─▶ 2 Validador ─▶ 3 Revisor final ─▶ 4 Pesquisa de preços ─▶ 5 Planilha
            (levanta)     (audita)       (decide e fecha)    (lojas, em paralelo)     (Excel)
```

Os passos 1 a 3 produzem a **lista** (nome, especificação, área de atuação e quantidade). O passo 4
acrescenta o **preço de mercado dos materiais**, com a loja, o link e a data de cada preço, e avisa
em quais lojas buscou. Serviços não recebem preço (a coluna fica em branco, para cotar com
empreiteiros).

## Entrada

`$ARGUMENTS` é o caminho de um PDF ou de uma pasta com o projeto. Se vazio, use os arquivos que
o usuário anexou na conversa (ficam em `~/.claude/uploads/...`). Formatos: PDF, PNG/JPG/WEBP,
TXT/MD/CSV. DWG, RVT e IFC não são lidos: peça a exportação em PDF.

## Passo 0: preparação

1. Defina `NOME` (nome curto da obra, sem espaços) e `SAIDA=cotacoes/<NOME>/`.
2. **Privacidade:** projetos de clientes têm direitos autorais e dados do local. Antes de gravar
   dentro do repositório, confira se ele é privado. Se for público, mantenha `projetos/<NOME>/` e
   `cotacoes/<NOME>/` fora do git (`.git/info/exclude`) e avise o usuário.
3. Prepare o material de leitura (renderiza cada prancha, gera recortes ampliados e extrai o texto):

```bash
python3 -I ${CLAUDE_SKILL_DIR}/scripts/preparar.py <projeto.pdf|pasta> <PREP>
```

`PREP` é uma pasta de trabalho (use o scratchpad). Ela recebe `*_pN_full.png`,
`*_pN_r{1,2}c{1,2,3}.png` e `texto.txt`.

## Passos 1 a 3: lista de materiais e serviços

Rode **em sequência**, cada um com a ferramenta `Agent` (tipo `general-purpose`, em segundo
plano). Os prompts completos estão em [references/agentes.md](references/agentes.md): copie o
modelo de cada etapa, troque os marcadores `{PDF}`, `{PREP}`, `{SAIDA}`, `{SCHEMA}`, `{CHECAR}` e
acrescente o que souber do projeto (tipo de obra, reforma ou obra nova, escopo).

| Etapa | Agente | Lê | Grava |
|---|---|---|---|
| 1 | Extrator | projeto | `{SAIDA}/etapa1_extrator.json` |
| 2 | Validador | projeto + etapa 1 | `{SAIDA}/etapa2_validador.json` |
| 3 | Revisor final | projeto + etapas 1 e 2 | `{SAIDA}/etapa3_final.json` |

Regras de orquestração:

- **Independência:** cada agente começa sem o contexto dos outros. O validador e o revisor recebem
  a lista como material a auditar, não como verdade.
- **Cobertura de leitura:** peça que cada agente informe quais recortes leu. Se declarar que leu só
  as imagens inteiras ou poucos recortes, reenvie a tarefa para as pranchas que ficaram de fora.
- **Esquema:** todo JSON segue `cotaai/schema.py`. Cada agente valida o próprio arquivo com
  `${CLAUDE_SKILL_DIR}/scripts/checar.py` até aparecer `OK`.
- Espere a notificação de cada agente antes de iniciar o seguinte. Não faça polling.

## Passo 4: pesquisa de preços de mercado (materiais)

Só começa depois que `etapa3_final.json` está pronto. Usa o agente **`pesquisador-de-precos`**
(definido em `.claude/agents/pesquisador-de-precos.md`) e o catálogo de lojas
[lojas.json](lojas.json) (Leroy Merlin, Telhanorte, Amoedo, Fluzão, Os Carvalhos, C&C, Obramax e,
como complemento, marketplaces). Peça ao usuário se quer incluir ou tirar lojas e atualize o
catálogo.

**4a. Teste de acesso (uma vez, antes de lançar os agentes).** Tente abrir a página inicial de cada
loja do catálogo com `WebFetch`, e uma busca de teste com `WebSearch` (`allowed_domains` = domínio
da loja). Classifique cada loja:

| Resultado do teste | Modo |
|---|---|
| `WebFetch` abre a página | `pagina_aberta`: o agente abre o produto e lê preço, validade e estoque |
| `WebFetch` falha (ex.: `ENOTFOUND`), mas a busca devolve páginas de produto | `somente_busca`: o preço vem do resultado da busca e pode estar desatualizado |
| Nada volta nem pelo domínio nem pelo nome | `sem_presenca_online`: cotar por telefone ou WhatsApp |

Se as lojas estiverem bloqueadas pela rede do ambiente, diga ao usuário que a leitura direta das
páginas exige liberar os domínios das lojas nas configurações de rede do ambiente (veja a
documentação do ambiente), e siga no modo `somente_busca`. Nunca contorne o bloqueio.

**4b. Dividir em lotes.**

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/lotes.py {SAIDA}/etapa3_final.json {SAIDA}/precos --tamanho 25
```

**4c. Rodar os agentes de preço em paralelo** (até 6 ao mesmo tempo, um por lote). Se o tipo
`pesquisador-de-precos` estiver disponível, use-o em `subagent_type`; senão use `general-purpose`
mandando ler e seguir `.claude/agents/pesquisador-de-precos.md`. Modelo de pedido:

```
LOTE:   {SAIDA}/precos/lote_NN_materiais.json
LOJAS:  .claude/skills/cotacao/lojas.json
SAIDA:  {SAIDA}/precos/precos_lote_NN.json
REGIAO: <cidade/UF da obra>, sites sem filtro de CEP salvo indicação
ACESSO: <resultado do teste 4a, loja por loja>
```

Rode primeiro **um lote piloto** e leia o resultado (preços com fonte? unidades convertidas? lojas
sem resultado?). Se o método estiver bom, lance os demais lotes. Só avance depois de todos
terminarem.

**4d. Juntar e conferir.**

```bash
python -m cotaai precos-mesclar {SAIDA}/precos/precos_lote_*.json --saida {SAIDA}/precos.json --final {SAIDA}/etapa3_final.json
```

O comando recusa lotes fora do esquema, ids repetidos, cotação sem link ou com preço inválido e
material sem registro de pesquisa. Corrija (reenvie o lote ao agente) e rode de novo.

**Regras de qualidade do passo 4** (confira ao ler os lotes):

- Toda cotação tem preço **visto** no texto da busca ou da página, com o link. Cotação sem origem é
  descartada.
- Preço por unidade do orçamento, com a conversão escrita (caixa = 2,20 m²).
- Cotação `aproximada` ou `sem estoque` aparece no detalhe, mas **não entra** nas estatísticas.
- Lojas sem resultado aparecem na aba "Lojas consultadas" com o motivo: o usuário precisa saber o
  que não foi pesquisado de fato.

## Passo 5: planilha final

```bash
python -m cotaai planilha {SAIDA}/etapa3_final.json
```

Usa `precos.json` automaticamente se existir ao lado. Gera `{SAIDA}/<NOME> - levantamento.xlsx`:

| Aba | Conteúdo |
|---|---|
| **Materiais** | quantidades e, para cada item, preço mínimo, médio e máximo, loja do menor preço, lojas pesquisadas, totais estimados e situação do preço |
| **Serviços** | nome, área de atuação, local, quantidade; valor em branco para cotar |
| **Preços (detalhe)** | uma linha por cotação: loja, produto, preço, conversão, equivalência, estoque, data e **link**. A coluna "Considerar" (Sim/Não) controla o que entra nos cálculos |
| **Lojas consultadas** | quais lojas foram pesquisadas, como (página aberta ou só busca), cobertura e totais |
| **Notas da IA** | pendências, premissas, itens removidos e materiais sem preço |

Entregue o arquivo ao usuário (SendUserFile) e responda com:

1. Totais: materiais, serviços, pendências e quantos materiais têm preço.
2. **Quais lojas foram pesquisadas e como**, e quais não deram resultado.
3. As pendências que precisam de decisão antes de cotar, em lista curta.
4. O aviso: quantitativos e preços são estimativas de IA. Os totais de preço somam só os materiais
   com preço encontrado, então o valor real é maior. Preços de sites variam por região, estoque e
   data: confirme com a loja antes de fechar.

## Sugestão ao usuário

Ao final, ofereça `/projeto3d` para gerar a visualização 3D da mesma obra (antes, obra e depois).
