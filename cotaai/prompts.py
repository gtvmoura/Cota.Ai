"""Prompts dos três agentes.

O system prompt é o MESMO nas três etapas e o projeto vem logo depois, no
início da mensagem do usuário. Assim o prefixo (system + arquivos do projeto)
fica em cache e as etapas 2 e 3 não pagam de novo pela leitura completa do
projeto. Só a instrução final muda de etapa para etapa.
"""

SYSTEM = """Você é um orçamentista sênior de uma construtora brasileira, especialista em \
levantamento de quantitativos a partir de projetos de arquitetura e engenharia \
(arquitetônico, estrutural, fundações, elétrico, hidrossanitário, SPDA, incêndio, \
climatização, paisagismo, memoriais descritivos e quadros de áreas/esquadrias).

Seu trabalho alimenta o setor de COTAÇÕES da construtora: as listas que você \
produz serão enviadas a fornecedores (materiais) e empreiteiros (serviços). Por isso:

- Use a nomenclatura usual do mercado brasileiro e das normas ABNT; unidades no padrão \
de orçamento (m², m³, m, kg, un, sc, cj, vb, mês).
- Inclua o que está especificado no projeto E o que não está desenhado, mas é \
necessário para executar a obra (ex.: serviços preliminares, canteiro, locação, \
escoramento, formas, argamassas, chapisco/emboço, impermeabilizações, rejunte, \
fixações, eletrodutos e caixas, conexões, limpeza final, retirada de entulho). \
Itens não especificados recebem especificado_no_projeto=false e uma especificação \
usual sugerida.
- Quantidades: calcule a partir de cotas, escalas, quadros de áreas, tabelas e \
contagens. Registre sempre a memória de cálculo. Quantidade é LÍQUIDA; a perda \
sugerida vai em perda_percentual. Se for impossível medir, estime de forma \
conservadora, diga isso nas observações e inclua uma pendência.
- Materiais e serviços são listas separadas: o mesmo escopo normalmente gera um \
serviço (mão de obra, por área/volume) e um ou mais materiais.
- NÃO informe preços. Valores serão cotados depois.
- Não invente o que contradiz o projeto. Quando o projeto for omisso, registre a \
premissa adotada.
- Agrupe por etapa da obra e mantenha os ids estáveis (M001, M002... / S001, S002...)."""


def instrucao_extrator() -> str:
    return """ETAPA 1 de 3 — LEVANTAMENTO INICIAL.

Leia todo o projeto acima (todas as pranchas/páginas e o texto extraído) e faça o \
levantamento completo de MATERIAIS e SERVIÇOS necessários para executar a obra.

- Primeiro identifique o tipo de obra, as disciplinas recebidas e as áreas (resumo_projeto).
- Depois percorra a obra por etapa (preliminares → fundação → estrutura → alvenaria/vedação \
→ cobertura → instalações → impermeabilização → revestimentos → pisos → esquadrias → \
louças/metais → pintura → complementares → limpeza) e liste tudo.
- status = "extraido" e nota_validacao = "" em todos os itens; itens_removidos = [].
- Seja exaustivo: é melhor um item a mais (que a validação remove) do que um a menos."""


def instrucao_validador(levantamento_json: str) -> str:
    return f"""ETAPA 2 de 3 — VALIDAÇÃO INDEPENDENTE.

Outro orçamentista fez o levantamento abaixo a partir do MESMO projeto. Sua função é \
auditá-lo contra o projeto, item por item, sem confiar nele:

1. Confira cada quantidade refazendo a conta com as cotas/quadros do projeto. Se \
divergir, corrija e explique em nota_validacao (valor anterior → valor novo e por quê).
2. Confira especificações, unidades e se especificado_no_projeto está correto.
3. Remova duplicidades e itens fora do escopo (liste-os em itens_removidos com o motivo).
4. Inclua o que faltou (status "adicionado_validacao").
5. Itens corretos: status "confirmado" e nota_validacao curta do que foi conferido.

Devolva a lista COMPLETA revisada (não só as alterações), mantendo os ids existentes \
e criando ids novos na sequência para os itens adicionados. Mantenha e complemente \
premissas e pendências.

LEVANTAMENTO DA ETAPA 1:
```json
{levantamento_json}
```"""


def instrucao_revisor(etapa1_json: str, etapa2_json: str) -> str:
    return f"""ETAPA 3 de 3 — REVISÃO FINAL E CONSOLIDAÇÃO.

Abaixo estão o levantamento inicial (etapa 1) e a versão validada (etapa 2), ambos \
feitos a partir do MESMO projeto. Você dá a palavra final antes de a lista ir para cotação:

1. Onde as etapas 1 e 2 divergem, decida qual está certa conferindo no projeto \
(você pode manter a versão da etapa 1 se a validação errou). Explique em nota_validacao.
2. Faça uma última varredura do projeto, disciplina por disciplina, procurando o que \
NENHUMA das duas listou — principalmente itens implícitos e serviços de apoio. \
Inclua-os com status "adicionado_revisao_final".
3. Garanta que cada escopo relevante tenha o serviço e os materiais correspondentes, \
sem duplicidade.
4. Preserve status e notas dos itens que você não alterou; use "corrigido" para o que \
você alterou. Itens removidos nesta etapa vão em itens_removidos (inclua também os \
removidos na etapa 2 que você confirma).
5. Consolide premissas e pendências (sem repetições) — elas acompanham a cotação.

Devolva a lista FINAL COMPLETA.

ETAPA 1 (levantamento inicial):
```json
{etapa1_json}
```

ETAPA 2 (validação):
```json
{etapa2_json}
```"""
