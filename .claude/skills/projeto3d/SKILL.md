---
name: projeto3d
description: Gera a visualização 3D interativa de uma obra a partir do projeto (PDF de arquitetura), com fases Antes, Obra (o que demolir e o que construir) e Depois (com mobiliário), paredes translúcidas conforme o ângulo, botões de orientação e bússola. Use quando o usuário digitar /projeto3d ou pedir modelo 3D, maquete, visualização, antes e depois ou representação 3D de um projeto.
argument-hint: "[caminho do projeto: arquivo PDF ou pasta]"
allowed-tools: Bash, Read, Write, Edit, Artifact
---

# /projeto3d: visualização 3D da obra (antes, obra e depois)

Produz uma página única (HTML com three.js) que o usuário gira, aproxima e alterna entre três fases.
Parte de um modelo-base pronto, em [assets/modelo-base.html](assets/modelo-base.html), que já traz
o visualizador completo. Seu trabalho é **modelar a obra** e preencher os parâmetros.

## O que o modelo-base já faz

- Fases **Antes** (existente), **Obra** (cinza = mantido, vermelho = demolir, verde = construir) e
  **Depois** (cores do projeto e mobiliário).
- Paredes entre a câmera e o interior ficam translúcidas, com caixa para ligar/desligar e controle
  de transparência.
- Botões "Ver de" Rua, Fundos, Esquerda e Direita, giro de 90°, Perspectiva, Planta, Fachada e uma
  bússola com seta para a rua.
- Lista lateral das intervenções: clicar num item aproxima a câmera e faz o grupo piscar.
- Temas claro e escuro, layout de celular, sem dependência além de three.js (cdnjs).

## Passo a passo

### 1. Ler o projeto

Prepare as pranchas e leia todas (plantas, cortes, fachadas, detalhes, legendas e quadros):

```bash
python3 -I ${CLAUDE_SKILL_DIR}/../cotacao/scripts/preparar.py <projeto.pdf|pasta> <PREP>
```

Use os recortes `*_pN_r{1,2}c{1,2,3}.png` para cotas e textos pequenos. Anote, por prancha:
dimensões externas, paredes (existentes, a demolir, a construir, com espessura), vãos (portas,
janelas, alturas), pisos e acabamentos (cores e materiais das legendas), forro e sanca, louças,
mobiliário e equipamentos com posição e medidas, fachada, pé-direito (se não houver, adote um valor,
diga qual e avise).

Se a mesma obra já passou por `/cotacao`, aproveite `etapa3_final.json` (áreas, esquadrias,
especificações) e as pendências.

### 2. Montar o modelo

1. Copie o modelo-base para `<SAIDA>/modelo-3d.html` (mesma pasta da cotação).
2. Substitua os marcadores: `{{TITULO}}` (nome da obra), `{{SUBTITULO}}` (tipo, área, revisão do
   projeto) e `{{NOTA}}` (o que é simplificado, premissas como pé-direito, cobertura omitida,
   "conferir medidas no local").
3. Edite o bloco `PROJ` no início do script (centro, raio das vistas, vista de fachada, rótulos dos
   ambientes).
4. Troque o bloco **GEOMETRIA DA OBRA** (a sala de exemplo) pela geometria real e a lista `itens`
   pelas intervenções reais. A referência das funções, as cores e as regras de modelagem estão em
   [references/guia-modelagem.md](references/guia-modelagem.md). Leia antes de modelar.

Padrão de qualidade esperado:

- **Fiel ao projeto:** medidas e posições das plantas, na mesma orientação (rua na parte de baixo da
  planta, `z` cresce para baixo).
- **Três fases coerentes:** tudo que é demolido aparece em "Antes" e some em "Depois"; tudo que é
  construído faz o inverso; cada item da lista lateral tem um `grupo` correspondente na geometria.
- **Mobiliário reconhecível**, não caixas: cada equipamento com forma própria (tampas de vidro,
  prateleiras, produtos, pés, puxadores), nas cores do projeto. Veja os exemplos no guia.
- **Cores do projeto** (legendas de pintura e revestimentos) em `corDepois`.
- Texto da interface em português do Brasil, descrições curtas citando prancha e detalhe.

### 3. Verificar visualmente

```bash
node ${CLAUDE_SKILL_DIR}/scripts/verificar.js <modelo-3d.html> <pasta_de_capturas>
```

Gera capturas das fases Antes, Obra e Depois e das vistas Rua e Direita e imprime erros de console.
Olhe as imagens: confira posições contra a planta, se a translucidez revela o interior, se os
rótulos e a bússola estão corretos e se o mobiliário está no lugar. Faça no máximo duas rodadas de
ajuste. Em ambiente sem acesso à internet, o script aceita `THREE_DIR` (veja o cabeçalho dele).

### 4. Publicar

Publique `modelo-3d.html` como Artifact (privado) e entregue o link. Descreva em uma frase o que
é e o que foi simplificado. Se o projeto for de cliente e o repositório for público, **não faça
commit** do modelo nem do projeto.

## Limites a avisar

- É um modelo simplificado a partir das pranchas, não um BIM: medidas de fachada, estrutura e
  detalhes não cotados são aproximadas.
- Pé-direito e cobertura costumam não constar; diga o valor adotado.
- Conferir medidas no local continua sendo necessário.

## Sugestão ao usuário

Se ainda não houver planilha de quantitativos desta obra, ofereça `/cotacao`.
