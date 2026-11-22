# Cota.Ai como plataforma: prompt mestre (v0) e sugestões

> Rascunho para alinhamento. Os pontos marcados com **[A DEFINIR]** dependem das respostas às
> perguntas de alinhamento. Depois das respostas, este documento vira a especificação da v1.

## 1. Onde estamos hoje

O repositório já tem o "cérebro" da Cota.Ai funcionando, mas só para quem usa o Claude Code ou a
linha de comando:

| Peça | Estado | Limitação para virar produto |
|---|---|---|
| Levantamento (extrator → validador → revisor) | Python + API da Anthropic, saída em JSON com esquema | Roda no terminal ou no GitHub Actions; o cliente não tem onde subir o projeto |
| Planilha Excel | Abas Materiais, Serviços, Notas, Preços, Lojas, Resumo financeiro | As cores hoje indicam **origem da validação** (corrigido/adicionado), não "explícito × inferido" |
| Pesquisa de preços | Agente do Claude Code com busca na web, lojas do RJ fixas em `lojas.json` | Depende da sessão do Claude Code; ~200 buscas por sessão; região fixa (RJ); não usa a localização da obra |
| Modelo 3D antes/depois | Página three.js gerada pela IA a partir das plantas | Modelagem manual pela IA a cada obra; sem "antes" a partir de fotos reais |
| Proposta comercial | DOCX/PDF no modelo da empresa | Igual: só no Claude Code |

Ou seja: **o motor existe; falta a casca (site, contas, fila de processamento, armazenamento) e
trocar o que hoje depende do Claude Code por chamadas de API.**

## 2. Arquitetura sugerida para a v1 (testável por clientes)

```
 Navegador (cliente)                 Backend                            Serviços
 ┌──────────────────┐   upload   ┌───────────────────┐  fila   ┌──────────────────────────┐
 │ Next.js (Vercel) │──────────▶ │ API (rotas Next)  │───────▶ │ Worker Python (o cotaai  │
 │ - login          │            │ - cria a obra     │         │ atual): extrator →       │
 │ - nova obra      │ ◀───────── │ - status em tempo │ ◀────── │ validador → revisor →    │
 │ - acompanhar     │  progresso │   real            │ eventos │ preços → 3D → planilha   │
 │ - planilha online│            └───────────────────┘         └──────────────────────────┘
 │ - visualizador 3D│                     │                               │
 │ - link p/ cliente│                     ▼                               ▼
 └──────────────────┘            Postgres + Storage             API Anthropic (Claude,
                                 (Supabase ou Neon + Blob)      web search/fetch), SINAPI,
                                                                Google Places, e-mail
```

- **Front:** Next.js na Vercel. Planilha exibida na própria página (filtros, cores, edição) e
  exportável para Excel/PDF.
- **Worker:** reaproveita `cotaai/` quase inteiro. Processos levam de 5 a 40 minutos, então rodam
  fora da requisição web (Vercel Workflow, ou um worker em Railway/Fly/Cloud Run). **[A DEFINIR]**
- **Preços sem Claude Code:** a etapa 4 passa a usar a API com as ferramentas de busca e leitura
  de páginas do servidor da Anthropic, mais fontes estruturadas (SINAPI, lojas com API).
- **Compartilhamento:** cada obra gera um link (privado, com senha ou por e-mail) para o cliente
  final ver a planilha e o 3D sem criar conta. **[A DEFINIR]**

## 3. Sugestões e alterações

### 3.1 Planilha
1. **Cor por origem do item, não pela validação.** Proposta de legenda:
   - Azul: explícito no projeto (cita prancha/página).
   - Laranja: inferido pela IA (necessário, mas não desenhado), com o motivo.
   - Cinza tracejado: premissa/estimativa a confirmar.
   - O histórico da validação (corrigido/adicionado) vira um ícone pequeno, não a cor da linha.
2. **Coluna de confiança** (alta/média/baixa) para o orçamentista saber o que conferir primeiro.
3. **Curva ABC**: destacar os 20% de itens que somam 80% do custo; é onde vale conferir a quantidade.
4. **Serviços com referência de mão de obra** (SINAPI/composições) mesmo sem cotação de empreiteiro,
   para dar uma ordem de grandeza.
5. **Visão por fornecedor**: exportar uma lista por loja/empreiteiro, pronta para enviar a cotação.

### 3.2 Pesquisa de preços pela localização da obra
1. O usuário informa **CEP/endereço da obra**; o sistema busca lojas num raio (Google Places) e
   mostra distância e mapa.
2. Três camadas de preço, sempre com fonte e data:
   - **SINAPI** (Caixa, oficial, por estado, mensal) como referência base para todos os itens.
   - **Lojas online com preço por CEP** (Leroy, Telhanorte, C&C, etc.), com link.
   - **Lojas locais sem site**: lista para cotar por WhatsApp; no futuro, envio automático de pedido
     de cotação e leitura da resposta.
3. Cache de preços por região (o mesmo cimento não precisa ser pesquisado em toda obra da semana).
   Reduz custo e tempo e cria uma base de preços própria, que é um diferencial do negócio.

### 3.3 3D antes e depois
1. **Antes**: além das plantas, aceitar **fotos do local** (e no futuro vídeo/varredura pelo
   celular) para o "antes" ser real, não só modelado.
2. **Depois**: manter o modelo three.js interativo (fases Antes / Obra / Depois, cores de
   demolir/construir) e acrescentar **imagens renderizadas fotorrealistas** de 2 ou 3 ângulos para
   a apresentação ao cliente final.
3. **Comparador lado a lado** com cortina deslizante e lista numerada das mudanças.
4. Se a construtora tiver IFC (Revit/ArchiCAD), importar direto, que é mais fiel do que ler o PDF.

### 3.4 Produto
1. **Revisão humana no meio do fluxo**: depois do levantamento, o orçamentista confirma as
   pendências antes de gastar com preços e 3D.
2. **Feedback por item** (correto/errado/quantidade errada) para medir a precisão e melhorar os prompts.
3. **Painel de custo por obra** (tokens + buscas) para definir o preço do plano.
4. **LGPD e sigilo**: projetos de clientes em armazenamento privado, por empresa, com exclusão sob
   pedido; nunca em repositório público.

## 4. Prompt mestre (v0) para construir a plataforma

Use este prompt numa sessão de desenvolvimento (Claude Code) depois das respostas às perguntas.

```
Você é o engenheiro principal da Cota.Ai, plataforma web brasileira que agiliza a cotação de
obras para construtoras e empreiteiras. O repositório já contém o motor em Python (pasta cotaai/):
levantamento de materiais e serviços em 3 etapas (extrator, validador, revisor) com saída JSON
validada por esquema, geração da planilha Excel, proposta comercial, e skills do Claude Code para
pesquisa de preços (.claude/skills/cotacao) e modelo 3D (.claude/skills/projeto3d).

OBJETIVO DA v1: transformar esse motor numa plataforma web que clientes externos testem sozinhos.

FLUXO DO USUÁRIO
1. Cria conta (empresa + usuários) [A DEFINIR: convite fechado ou cadastro livre].
2. "Nova obra": nome, tipo [reforma/obra nova/...], endereço ou CEP da obra, upload dos arquivos
   (PDF, imagens, memorial; fotos do local opcionais).
3. Acompanha o progresso em tempo real por etapa: leitura → levantamento → validação → revisão →
   [checkpoint humano] → preços → 3D → planilha final.
4. Recebe:
   a) Planilha online e em Excel: Materiais e Serviços, com legenda de cores
      AZUL = explícito no projeto (com prancha/página), LARANJA = inferido pela IA (com motivo),
      CINZA = premissa a confirmar; coluna de confiança; curva ABC; memória de cálculo.
   b) Pesquisa de preços por material: SINAPI da UF da obra + lojas próximas ao endereço da obra
      (nome, distância, preço, link, data, estoque) + mínimo/médio/máximo; nunca inventar preço;
      itens sem preço ficam marcados "não encontrado".
   c) Visualizador 3D antes/obra/depois com as principais mudanças numeradas e destacadas,
      comparador lado a lado e imagens de apresentação.
5. Compartilha um link de visualização com o cliente final [A DEFINIR: permissões].

REQUISITOS TÉCNICOS
- Front: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui, em português do Brasil,
  responsivo (celular é prioridade para o canteiro).
- Backend: rotas do Next para a API; worker Python reaproveitando cotaai/ para os processos longos
  (fila com retentativa, retomada de onde parou, como o pipeline atual já faz).
- Dados: Postgres (empresas, usuários, obras, execuções, itens, preços, lojas) + armazenamento
  privado de arquivos por empresa.
- IA: API da Anthropic (modelo configurável), com cache do projeto entre as etapas, saída por
  esquema JSON, ferramentas de busca e leitura de páginas no servidor para preços.
- Preços: módulo de fontes plugáveis (SINAPI, lojas online, Google Places para lojas locais),
  cache por região com validade, registro de fonte, link e data em toda cotação.
- 3D: gerar a cena a partir do JSON de geometria (paredes, vãos, ambientes, intervenções), não de
  HTML escrito à mão; three.js no navegador.
- Observabilidade: custo (tokens e buscas) e duração por obra e por etapa.
- Segurança: isolamento por empresa em todas as consultas, URLs assinadas para arquivos, LGPD.
- Testes: manter os testes atuais do pipeline e cobrir API, fila e permissões.

ENTREGAS EM ORDEM
1. Esqueleto web + login + upload + fila + levantamento (etapas 1–3) + planilha online/Excel.
2. Preços por localização (SINAPI + lojas online + lojas próximas).
3. 3D antes/depois a partir de geometria JSON + link de compartilhamento.
4. Proposta comercial dentro da plataforma, feedback por item e painel de custos.

Antes de codar cada entrega, apresente o plano, as tabelas do banco e as telas; depois implemente
com testes e um roteiro de verificação manual.
```

## 5. Riscos a ter no radar

- **Precisão do quantitativo** é o que decide a confiança do cliente; precisamos de 3 a 5 projetos
  reais com orçamento já fechado para medir o erro antes de abrir para testes.
- **Preço de loja muda e depende do CEP**; sem fonte e data, o número perde credibilidade.
- **Raspagem de sites de lojas** pode violar termos de uso; preferir APIs, parcerias e SINAPI.
- **Custo por obra** (tokens de PDFs grandes + muitas buscas) precisa caber no preço do plano.
- **3D a partir de PDF** é aproximado; deixar claro que é ilustrativo, não executivo.
