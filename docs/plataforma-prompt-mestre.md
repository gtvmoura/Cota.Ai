# Cota.Ai como plataforma: prompt mestre e sugestões

> Versão 2 do alinhamento (22/11/2026). As decisões estão na seção 0 e a infraestrutura escolhida
> (opção A, só planos gratuitos) na seção 5.

## 0. Decisões do alinhamento

| Tema | Decisão |
|---|---|
| Cliente | Construtoras e empreiteiras pequenas e médias |
| Obras | Todos os tipos |
| Quem usa | Todos: dono, orçamentista e engenheiro (cotar, ver a obra, mandar o 3D ao cliente final) |
| Cobrança | Por obra ou assinatura mensal (definir depois dos testes) |
| Região inicial | Rio de Janeiro |
| Concorrência hoje | Planilha manual |
| Entrada | PDF de projeto, obrigatório. Sem projeto, não processa. Fotos do local são opcionais |
| Legenda da planilha | Azul = explícito no projeto, laranja = inferido pela IA, cinza = premissa a confirmar |
| Modelo da planilha | Formato próprio da Cota.Ai |
| Serviços | Preço de referência (SINAPI), editável pelo empreiteiro |
| Formatos de saída | Planilha online, Excel e PDF |
| Lojas | Raio de busca escolhido pelo usuário; SINAPI como referência oficial |
| Pedido de cotação automático (WhatsApp/e-mail) | Fica para depois da v1 |
| Tempo de resposta | Até algumas horas é aceitável; quanto mais rápido, melhor |
| 3D | Modelo interativo, primeiro para o cliente final ver a obra; destaque para demolição e construção; "antes" pelas plantas e pelas fotos quando houver |
| Plataforma | Web responsiva primeiro; app depois |
| Acesso | Só por convite; um usuário por empresa no início |
| Link para o cliente final | Link de visualização sem login, com prazo de validade e opção de revogar (decisão minha, pode mudar) |
| Marca | Ainda sem manual; criamos uma identidade simples na v1 |
| Teste grátis | 1 obra por cliente |
| Custos fixos | Zero: só planos gratuitos; o único gasto é a API da Anthropic |
| Infraestrutura | Opção A com planos gratuitos: Vercel Hobby + Supabase Free + GitHub Actions como worker |
| Endereço | Subdomínio gratuito da Vercel (ex.: `cota-ai.vercel.app`) até existir domínio próprio |
| Precisão | Há projetos reais com orçamento fechado para medir o erro antes dos testes |
| Sigilo | Prevenir sempre: dados isolados por empresa, arquivos privados, LGPD |

**Prioridade recomendada (perguntas 38 e 39):**

1. **Entrega 1 (semanas 1–3):** login por convite, upload, levantamento em 3 etapas, planilha online
   e Excel com a legenda nova. É o que mostra valor sozinho e permite medir a precisão.
2. **Entrega 2 (semanas 3–5):** preços com SINAPI e lojas pelo CEP da obra.
3. **Entrega 3 (semanas 5–7):** 3D antes/depois com link para o cliente final.
4. **Depois:** proposta comercial (já existe no motor e entra fácil), pedido de cotação
   automático, app.

**BDI (pergunta 16):** é o percentual que a construtora soma ao custo direto (materiais + mão de
obra) para cobrir despesas indiretas (administração, seguros, garantia, riscos), impostos e lucro.
Em obras privadas costuma ficar entre 20% e 35%. A proposta: a planilha mostra o custo direto e
tem um campo opcional de BDI, que gera o preço de venda.

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
  fora da requisição web, no GitHub Actions deste repositório privado, disparado pelo site
  (veja a seção 5).
- **Preços sem Claude Code:** a etapa 4 passa a usar a API com as ferramentas de busca e leitura
  de páginas do servidor da Anthropic, mais fontes estruturadas (SINAPI, lojas com API).
- **Compartilhamento:** cada obra gera um link de visualização sem login, com validade e opção de
  revogar, para o cliente final ver o 3D (e, se o construtor quiser, a planilha sem preços).

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
5. **Repositório:** o projeto foi migrado em 22/11/2026 do repositório público `gtvmoura/Cota.Ai`
   para o privado `gtvmoura/cota-a-`. Mesmo privado, projetos e planilhas de clientes ficam só no
   armazenamento privado da plataforma (Supabase), nunca em commits nem em logs do GitHub Actions.

## 4. Prompt mestre para construir a plataforma

Use este prompt numa sessão de desenvolvimento (Claude Code) depois das respostas às perguntas.

```
Você é o engenheiro principal da Cota.Ai, plataforma web brasileira que agiliza a cotação de
obras para construtoras e empreiteiras. O repositório já contém o motor em Python (pasta cotaai/):
levantamento de materiais e serviços em 3 etapas (extrator, validador, revisor) com saída JSON
validada por esquema, geração da planilha Excel, proposta comercial, e skills do Claude Code para
pesquisa de preços (.claude/skills/cotacao) e modelo 3D (.claude/skills/projeto3d).

OBJETIVO DA v1: transformar esse motor numa plataforma web que clientes externos testem sozinhos.

FLUXO DO USUÁRIO
1. Entra por convite (uma empresa, um usuário no início; 1 obra grátis de teste).
2. "Nova obra": nome, tipo (qualquer tipo de obra), endereço ou CEP da obra (região inicial: RJ),
   raio de busca de lojas, upload do projeto em PDF (obrigatório; sem projeto não processa),
   memorial e fotos do local (opcionais).
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
5. Compartilha com o cliente final um link de visualização sem login, com validade e revogável.
6. Serviços vêm com preço de referência SINAPI que o empreiteiro pode alterar; campo opcional de
   BDI gera o preço de venda. Saídas: planilha online, Excel e PDF.

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

## 5. Infraestrutura escolhida: opção A só com planos gratuitos

Decisão: **Vercel + Supabase**, sem pagar nada além da IA. Como os planos gratuitos têm limites,
a arquitetura se ajusta assim:

| Peça | Serviço (grátis) | Limite que importa | Como contornamos |
|---|---|---|---|
| Site | Vercel Hobby | Uso não comercial; funções de no máximo alguns minutos | O site só recebe o upload e mostra os resultados; o processamento longo vai para o worker. **Ao começar a cobrar, migrar para o Vercel Pro (US$ 20/mês)**, exigido pelos termos |
| Login, banco e arquivos | Supabase Free | 2 projetos grátis **por conta**; 500 MB de banco e 1 GB de arquivos; projeto pausa após 7 dias sem uso; e-mail embutido envia poucos convites por hora | Ver o aviso abaixo sobre os seus outros projetos; apagar PDFs após o processamento e guardar só os resultados; convites são poucos nos testes |
| Worker (processos de 5–40 min) | **GitHub Actions** do repositório privado | 2.000 minutos/mês grátis em repositório privado (cerca de 50–100 obras) | O site dispara o workflow; ele baixa o PDF do Supabase, roda o `cotaai/`, devolve os resultados ao Supabase e não grava nada no repositório |
| CEP → endereço | ViaCEP | Grátis, sem chave | — |
| Lojas próximas | OpenStreetMap (Nominatim/Overpass) | Grátis, cobertura irregular de lojas pequenas | Complementar com a lista de lojas do RJ que já temos; Google Places só se precisar (pede cartão) |
| Preço de referência | SINAPI (Caixa) | Grátis, planilhas mensais por estado | Importar a tabela do RJ uma vez por mês |
| Erros | Sentry Developer | 5 mil erros/mês | — |
| Endereço do site | `*.vercel.app` | — | Domínio próprio (cerca de R$ 40/ano) quando quiser |

**Suas contas gratuitas já em uso (resposta à sua pergunta):**

- **Vercel:** não muda nada. O plano Hobby aceita vários projetos; a Cota.Ai vira mais um.
- **Supabase:** **pode mudar.** O plano gratuito permite **2 projetos ativos por conta**. Se os seus
  outros projetos já ocupam as duas vagas, há três saídas: pausar um deles, criar uma conta nova
  do Supabase só para a Cota.Ai (recomendado: separa os dados dos clientes dos outros projetos) ou
  usar o Neon (Postgres grátis) para o banco. Os projetos grátis também pausam depois de 7 dias
  sem acesso; na fase de testes, isso só atrasa o primeiro acesso depois da pausa.

**Custo mensal fixo: R$ 0.** Único gasto: a API da Anthropic (seção 6).

### Outras opções avaliadas (para o futuro)


Valores aproximados em dólar; confira nos sites antes de contratar.

| Opção | Como fica | Prós | Contras | Custo mensal na fase de testes |
|---|---|---|---|---|
| **A paga. Vercel Pro + Supabase Pro + worker no Railway** (quando houver receita) | Site Next.js na Vercel; login, banco Postgres e arquivos no Supabase; o motor `cotaai/` roda num worker no Railway | Mais rápida de construir; cada peça é especialista; Supabase traz login, banco e arquivos privados com regras por empresa | Três contas e três faturas | US$ 0–70 (Vercel Pro US$ 20 para uso comercial, Supabase Pro US$ 25, Railway US$ 5–20) |
| **B. Google Cloud** (Cloud Run + Firebase Auth + Cloud SQL ou Firestore + Cloud Storage) | Tudo no Google; site e worker em contêineres | Uma fatura; programa Google for Startups dá créditos; Google Maps/Places no mesmo lugar | Mais configuração; painel mais complexo | US$ 20–80 (ou zero com créditos) |
| **C. AWS** (Amplify ou ECS + Cognito + RDS + S3) | Equivalente à B, na Amazon | Padrão de mercado; créditos do AWS Activate | A mais trabalhosa de montar e manter | US$ 30–100 (ou zero com créditos) |
| **D. Tudo em Python** (FastAPI ou Django + HTMX no Render ou Fly.io + Postgres gerenciado) | Um só código, na mesma linguagem do motor atual | Menos peças; reaproveita tudo; mais barata | Interface menos rica (planilha editável e 3D pedem mais JavaScript à mão) | US$ 15–40 |
| **E. Low-code no front** (Bubble ou FlutterFlow) + worker Python | Telas montadas sem código; o motor continua em Python | Você mesmo ajusta as telas | Limitada para o 3D e a planilha; fica presa à ferramenta; caro ao crescer | US$ 30–120 |
| **Complemento: Managed Agents (Anthropic)** | Os agentes (preços, 3D) rodam num ambiente da própria Anthropic, em vez de no nosso worker | Menos servidor para manter; bom para os agentes de busca longa | Em beta; cobra tempo de sessão além dos tokens | Por uso |

Itens comuns a todas: domínio `.com.br` (cerca de R$ 40/ano), e-mail transacional (Resend ou
similar, gratuito até alguns milhares de e-mails), Google Places para lojas próximas (há cota
gratuita mensal que cobre os testes) e monitoramento de erros (Sentry, plano gratuito).

## 6. Custo estimado por obra e orçamento dos testes (pergunta 34)

Preços da API da Anthropic por milhão de tokens: Claude Opus 5.5 US$ 4 de entrada e US$ 20 de
saída (leitura em cache US$ 0,20); Claude Sonnet 5.5 US$ 2 e US$ 10. Cada busca na web tem custo
próprio além dos tokens (confira o valor atual na página de preços).

Estimativa para uma obra média (cerca de 30 pranchas e 120 materiais):

| Etapa | Modelo sugerido | Custo estimado |
|---|---|---|
| Levantamento (3 etapas, projeto em cache) | Opus 5.5 | US$ 2–4 (projeto grande, 100+ pranchas: US$ 8–12) |
| Pesquisa de preços (~300 buscas e leitura das páginas) | Sonnet 5.5 | US$ 5–10 (cai muito com o cache de preços por região) |
| 3D (geometria + 1 ou 2 rodadas de ajuste) | Opus 5.5 | US$ 1–3 |
| **Total por obra** | | **US$ 8–17 (R$ 45–95)** |

Orçamento da fase de testes, com infraestrutura grátis: **só a IA, cerca de US$ 8–17 por obra**.
Com 20 obras no mês (incluindo as de calibração), algo como US$ 160–340 (R$ 900–1.900). Para
controlar, a plataforma terá um teto mensal de gasto e a obra grátis de cada cliente usa limites
menores de busca de preços. Esses números precisam ser confirmados rodando os projetos reais que você tem: o
painel de custo por obra (seção 3.4) mede isso desde o primeiro dia.

Para o preço de venda: com custo de R$ 50–100 por obra, cobrar R$ 300–600 por obra ou uma
assinatura com franquia de obras deixa margem confortável.

## 7. Riscos a ter no radar

- **Precisão do quantitativo** é o que decide a confiança do cliente; precisamos de 3 a 5 projetos
  reais com orçamento já fechado para medir o erro antes de abrir para testes.
- **Preço de loja muda e depende do CEP**; sem fonte e data, o número perde credibilidade.
- **Raspagem de sites de lojas** pode violar termos de uso; preferir APIs, parcerias e SINAPI.
- **Custo por obra** (tokens de PDFs grandes + muitas buscas) precisa caber no preço do plano.
- **3D a partir de PDF** é aproximado; deixar claro que é ilustrativo, não executivo.
