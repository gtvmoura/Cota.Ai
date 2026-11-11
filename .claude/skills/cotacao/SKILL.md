---
name: cotacao
description: Levantamento de materiais e serviços para cotação a partir de um projeto de arquitetura ou engenharia (PDF, imagens, memorial). Roda três agentes especializados em sequência (extrator, validador, revisor final) e entrega uma planilha Excel com as abas Materiais e Serviços. Use quando o usuário digitar /cotacao, anexar um projeto pedindo cotação, orçamento, levantamento de quantitativos ou lista de materiais e serviços.
argument-hint: "[caminho do projeto: arquivo PDF ou pasta]"
allowed-tools: Bash, Read, Write, Agent
---

# /cotacao: levantamento de materiais e serviços

Transforma um projeto em uma planilha pronta para cotar. Três agentes independentes leem o
projeto: o 1º levanta, o 2º audita, o 3º decide as divergências e procura o que faltou. Valores
não são preenchidos; só nome, especificação, área de atuação e quantidade.

## Entrada

`$ARGUMENTS` é o caminho de um PDF ou de uma pasta com o projeto. Se vazio, use os arquivos que
o usuário anexou na conversa (ficam em `~/.claude/uploads/...`). Formatos: PDF, PNG/JPG/WEBP,
TXT/MD/CSV. DWG, RVT e IFC não são lidos: peça a exportação em PDF.

## Antes de começar

1. Defina `NOME` (nome curto da obra, sem espaços) e `SAIDA=cotacoes/<NOME>/`.
2. **Privacidade:** projetos de clientes têm direitos autorais e dados do local. Antes de gravar
   dentro do repositório, confira se ele é privado (`gh`/API). Se for público, mantenha
   `projetos/<NOME>/` e `cotacoes/<NOME>/` fora do git (`.git/info/exclude`) e avise o usuário.
3. Prepare o material de leitura (renderiza cada prancha, gera recortes ampliados e extrai o texto):

```bash
python3 -I ${CLAUDE_SKILL_DIR}/scripts/preparar.py <projeto.pdf|pasta> <PREP>
```

`PREP` é uma pasta de trabalho (use o scratchpad). Ela recebe `*_pN_full.png`,
`*_pN_r{1,2}c{1,2,3}.png` e `texto.txt`.

## Os três agentes

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

- **Independência:** cada agente começa sem o contexto dos outros. Não passe a conclusão de um
  como verdade ao próximo; o validador e o revisor recebem a lista como material a auditar.
- **Cobertura de leitura:** peça que cada agente informe quais recortes leu. Se um agente
  declarar que leu só as imagens inteiras ou poucos recortes, reenvie a tarefa para as pranchas
  que ficaram de fora (validador e revisor devem cobrir as lacunas do anterior).
- **Esquema:** todo JSON segue `cotaai/schema.py` (campos obrigatórios, sem extras). Cada agente
  valida o próprio arquivo com `${CLAUDE_SKILL_DIR}/scripts/checar.py` até aparecer `OK`.
- Espere a notificação de cada agente antes de iniciar o seguinte. Não faça polling.

## Planilha final

```bash
python -m cotaai planilha {SAIDA}/etapa3_final.json
```

Gera `{SAIDA}/<NOME> - levantamento.xlsx` com as abas **Materiais**, **Serviços** e **Notas da IA**
(pendências, premissas e itens removidos). Cores: amarelo = corrigido, azul = adicionado na
validação, verde = adicionado na revisão final. Se o módulo `cotaai` não estiver disponível,
instale `openpyxl` e gere pelo `cotaai/planilha.py` do repositório.

Entregue o arquivo ao usuário (SendUserFile) e responda com:

1. Totais: materiais, serviços e pendências.
2. As correções e acréscimos mais relevantes das etapas 2 e 3.
3. As **pendências** que precisam de decisão antes de cotar, em lista curta.
4. O aviso de que os quantitativos são estimativas de IA e devem ser conferidos nos itens de
   maior valor, com base na memória de cálculo de cada linha.

## Sugestão ao usuário

Ao final, ofereça `/projeto3d` para gerar a visualização 3D da mesma obra (antes, obra e depois).
