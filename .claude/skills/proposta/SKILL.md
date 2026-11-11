---
name: proposta
description: Monta a proposta comercial (DOCX e PDF) de uma obra no modelo da empresa, a partir do escopo validado e da planilha com os valores informados. Escreve o memorial descritivo, observações, exclusões, valor total por extenso, prazo, pagamento e responsabilidades, com os dados do cliente. É uma etapa separada da /cotacao. Use quando o usuário digitar /proposta ou pedir proposta comercial, orçamento para enviar ao cliente ou revisão de proposta.
argument-hint: "[pasta da obra, ex.: cotacoes/casa-silva]"
allowed-tools: Bash, Read, Write, Agent, AskUserQuestion
---

# /proposta: proposta comercial a partir do escopo e dos valores validados

Esta etapa vem **depois** da `/cotacao`. A cotação levanta o que a obra precisa e o que custa no
mercado; a proposta é o documento que a construtora envia ao cliente, com o escopo descrito e o valor
fechado pela própria empresa.

```
 /cotacao  ─▶  planilha  ─▶  VOCÊS validam e informam os valores  ─▶  /proposta  ─▶  DOCX + PDF
 (escopo, quantidades,        (preço adotado dos materiais,          (memorial, valor,
  preços de mercado)           valor unitário dos serviços)           prazo, pagamento)
```

**Regra central:** os valores da proposta vêm só da planilha que a equipe validou e preencheu. Você nunca
inventa nem arredonda preço, e nunca marca a proposta como `final` sem a confirmação expressa do
responsável de que quantidades e valores foram validados.

## Pré-requisitos

- Pasta da obra (`$ARGUMENTS`, por exemplo `cotacoes/<obra>/`) com `etapa3_final.json` e a planilha
  `*levantamento*.xlsx` (de preferência com `precos.json` ao lado). Se faltar, avise que a `/cotacao` vem antes.
- Modelo da empresa em `empresa/empresa.json` (logo em `empresa/logo.png`). Se não existir, mostre o
  `.claude/skills/proposta/assets/empresa.exemplo.json`, peça os dados reais (nome, responsável,
  contatos, rodapé, textos-padrão, forma de pagamento) e o logo, e grave o arquivo. Essa pasta fica
  fora do git: tem dados da empresa e do responsável.

## Passo a passo

### 1. Criar os arquivos da proposta

```bash
python -m cotaai proposta-init <pasta da obra>
```

Cria `<pasta>/proposta/proposta.json` (dados da proposta) e `proposta_conteudo.json` (rascunho do
memorial, um grupo por área de atuação). Se já existirem, mantém.

### 2. Dados da proposta

Pergunte (AskUserQuestion, só o que ainda não souber) e grave em `proposta.json`:

| Campo | O que é |
|---|---|
| `cliente` | nome, "aos cuidados de", telefone, e-mail |
| `numero` e `ano` | número sequencial da proposta da empresa (gera `CB022/2026`); `revisao` (0, 1, 2...) |
| `data` | data da proposta (AAAA-MM-DD) |
| `tipo_obra` | "Reforma comercial", "Obra nova residencial"... (entra na frase de abertura) |
| `referencia` | "Orçamento Serviço" ou o assunto |
| `projeto_referencia` | arquivo e data do projeto base ("PROJETO-ARQ-R0 de 31/07/26") |
| `prazo_dias` | prazo de entrega em dias corridos |
| `pagamento` | parcelas (padrão da empresa, ou outras: `rotulo`, `percentual`, `quando`; `percentual: null` = restante) |
| `valores.modo` | `global` (um valor total, como no modelo) ou `detalhado` (materiais e mão de obra por área) |
| `valores.acrescimos` | por exemplo BDI em % sobre o subtotal, se a empresa usa |
| `valores.valor_final_manual` | só se o responsável decidir um valor fechado diferente da soma (por exemplo, arredondado) |
| `valores.mostrar_valor_parcelas` | mostra o valor em R$ de cada parcela |
| `validade_dias` | validade da proposta, se houver |

### 3. Conferir os valores com o responsável

```bash
python -m cotaai proposta <pasta da obra> --verificar
```

Mostra materiais, serviços por área, acréscimos e total, e lista o que falta (materiais sem preço
adotado, serviços sem valor unitário). Itens sem valor ficam **fora** do total: mostre isso ao usuário e
peça para preencher na planilha ou confirmar que ficam de fora (`permitir_itens_sem_valor`). Não
preencha valores por conta própria.

### 4. Redigir o memorial

Use o agente `redator-de-proposta` (`.claude/agents/redator-de-proposta.md`). Se o tipo não estiver
disponível, use `general-purpose` mandando ler e seguir esse arquivo. Pedido:

```
FINAL:    <pasta>/etapa3_final.json
PROPOSTA: <pasta>/proposta/proposta.json
EMPRESA:  empresa/empresa.json
RASCUNHO: <pasta>/proposta/proposta_conteudo.json
SAIDA:    <pasta>/proposta/proposta_conteudo.json
PROJETO:  texto extraído do projeto (opcional)
```

Leia o resultado: o memorial segue a ordem da obra? Há item que dependa de pendência não resolvida?
As exclusões estão coerentes com o que a planilha inclui no preço?

### 5. Gerar o rascunho e revisar

```bash
python -m cotaai proposta <pasta da obra> --pdf
```

Gera `<pasta>/proposta/<CÓDIGO> - <CLIENTE> - PROPOSTA REV NN (RASCUNHO).docx` e `.pdf`, com a faixa
"RASCUNHO" no cabeçalho. Renderize as páginas do PDF em imagem e confira: logo, código e data, dados do
cliente, memorial, valores (e o valor por extenso), prazo, pagamento, responsabilidades e assinatura.
Entregue o DOCX e o PDF ao usuário (SendUserFile) com um resumo curto: total, o que está incluído e
excluído, e as dúvidas de escopo.

### 6. Versão final e revisões

Só quando o responsável disser expressamente que quantidades e valores estão validados e que a proposta
pode seguir:

1. `status: "final"` e `validado_por: "<nome de quem validou>"` em `proposta.json`.
2. `python -m cotaai proposta <pasta> --pdf`. A versão final não sai com pendências (valores faltando,
   pagamento que não fecha 100%, cliente em branco).

Para uma **revisão** (cliente pediu mudança), aumente `revisao` e a `data`: os arquivos anteriores
ficam guardados e o novo sai como `REV NN`. Ajuste o valor pela planilha ou por `valor_final_manual`.

## Modelo do documento

Segue a proposta de referência da empresa: ofício com código, data, destinatário e caixa "PROPOSTA
COMERCIAL-REVISÃO NN"; memorial descritivo numerado por disciplina; observações (projeto de referência e
inclusões); exclusões; considerações gerais; valor total (tabela, no modo detalhado) com extenso; prazo;
pagamento; responsabilidades do contratado e do contratante; assinatura. Logo no cabeçalho e rodapé com
contatos e barra de cor, definidos em `empresa.json`. Para mudar texto-padrão, cláusulas ou rodapé,
edite `empresa/empresa.json`; para mudar o layout, `cotaai/proposta.py`.
