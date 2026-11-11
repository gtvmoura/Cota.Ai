# Guia de modelagem do modelo-base

## Convenções

- Unidade da geometria: **centímetros**. A cena é escalada para metros (`root.scale = 0.01`); os
  parâmetros de `PROJ` (centro, raio, fachada) são em **metros**.
- Eixos: `x` para a direita da planta, `z` para **baixo** da planta (a rua fica em `z` grande, é o
  "lado da rua"), `y` para cima. Origem no canto superior esquerdo da planta.
- `H` é o pé-direito e `V` a altura dos vãos (`const H=300, V=210`). Ajuste ao projeto.
- Paredes: o bloco interno do contorno fica em `0..L`; a espessura da parede é desenhada para fora
  (por exemplo, `box(-15,0,…)` para a parede esquerda).

## Funções

```js
box(x1,x2, z1,z2, y1,y2, fase, corAntes, corDepois, grupo, alpha)
seg(xa,za, xb,zb, espessura, y1,y2, lado, fase, corAntes, corDepois)   // parede inclinada (lado = +1 ou -1)
piso([[x,z],…], corAntes, corDepois, fase, grupo)                       // polígono no chão; fase 'N' sobe 0,6 cm
F(x1,x2, z1,z2, y1,y2, cor, alpha)                                      // mobiliário (fase 'F')
cyl(x,z, y1,y2, raio, cor, fase, alpha)                                 // cilindro
reg(mesh, fase, corAntes, corDepois, grupo, alpha)                      // registra qualquer THREE.Mesh
```

Para formas especiais (arcos, vãos curvos) crie um `THREE.Shape` + `ExtrudeGeometry`, posicione e
passe por `reg(...)`. Exemplo: vão com arco de 2,00 m de largura e 2,00 m de altura nas laterais:

```js
const vao=new THREE.Shape(); vao.moveTo(45,0); vao.lineTo(245,0); vao.lineTo(245,200);
vao.quadraticCurveTo(145,260,45,200); vao.closePath();           // arco: ponto de controle acima das laterais
const m=new THREE.Mesh(new THREE.ExtrudeGeometry(vao,{depth:15,bevelEnabled:false,curveSegments:16}));
m.position.z=845;                                                // profundidade da parede da fachada
reg(m,'D',C.reboco,C.reboco,'d-fachada');
```

## Fases

| fase | significado | Antes | Obra | Depois |
|---|---|---|---|---|
| `K` | existente, mantido | sim | cinza | sim, com `corDepois` |
| `D` | demolir ou remover | sim | vermelho | não |
| `N` | construir ou instalar | não | verde | sim |
| `F` | mobiliário | não | não | sim (caixa "Mobiliário") |

`corAntes` é a cor do estado atual; `corDepois` é a cor do acabamento final (pintura, revestimento).
Um mesmo trecho que ganha pintura é `K` com `corAntes` ≠ `corDepois`.

## Grupos e lista lateral

Cada item de `itens` (`[grupo, 'D'|'N', título, descrição]`) precisa de ao menos um elemento com o
mesmo `grupo` na geometria. Fases `D` e `N` sem `grupo` não aparecem na lista. Use um `grupo` por
intervenção do projeto ("construir/demolir" da prancha), com o texto da própria prancha.

## Cores do projeto

Converta as legendas de pintura e revestimento para `0xRRGGBB` e coloque em `C` (paleta no início
do script). Use o RGB indicado na legenda quando houver (por exemplo, Pantone 219C ≈ `0xec008c`).

## Modelar vãos

Uma parede com vão vira vários `box`: trechos cheios + trecho acima do vão (`V..H`) + o vão
(porta ou janela como elemento próprio). Para um vão a abrir (demolição), o trecho do vão é `D`; a
porta nova é `N`; o que ficar acima do vão é `K`.

## Mobiliário reconhecível

Monte cada equipamento com partes. Padrões usados na obra de referência:

- **Freezer de sorvete ou picolé:** base escura recuada, corpo, tampo, bandejas com produtos
  coloridos em grade, tampas de vidro deslizantes (alpha 0,4) inclinadas em duas folhas.
- **Buffet com protetor de vidro:** o freezer acima + vidro frontal, tubos de inox nos cantos e
  perfil de LED no topo.
- **Geladeira vertical:** corpo, porta de vidro, prateleiras e produtos por nível, puxador.
- **Bancada de inox:** tampo, espelho traseiro, cuba, torneira, prateleira inferior e quatro pés.
- **Balcão de caixa:** corpo na cor do projeto, tampo branco, vitrine de bomboniere com potes
  (cilindros), monitor e gaveta.
- **Estante e prateleiras aéreas:** montantes finos e tábuas com caixas em tons variados.

Use paleta pequena para produtos (rosa, marrom, creme, verde, laranja) variando por índice. Mantenha
as arestas discretas: o modelo já reduz a opacidade das linhas do mobiliário.

## Armadilhas

- Elemento sem `fase` correta não aparece na fase esperada.
- Parede = elemento `K`/`D`/`N` com altura >= 90 cm e espessura <= 35 cm. Coisas baixas ou grossas
  (muretas de 1 m com 20 cm contam como parede; bancadas e pilares grossos não) não ficam translúcidas.
- Sem acesso às fontes do Google ou ao CDN em ambientes fechados: a página tem fallback de fontes, mas
  o three.js é necessário (cdnjs e jsdelivr).
- Se o projeto não tem pé-direito, adote 2,80 a 3,00 m e informe na nota.
