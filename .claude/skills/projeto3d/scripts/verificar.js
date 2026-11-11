/* Abre o modelo 3D num Chromium sem interface e salva capturas das fases e das vistas.
 *
 *   node verificar.js <modelo-3d.html> <pasta_de_capturas>
 *
 * Gera: antes.png, obra.png, depois.png, rua.png, direita.png e imprime erros de console.
 * Requer o pacote "playwright" (já presente no ambiente do Claude Code).
 *
 * Ambiente sem internet: baixe o three.js uma vez e informe a pasta em THREE_DIR:
 *   npm pack three@0.128.0 && tar xzf three-0.128.0.tgz package/build/three.min.js \
 *     package/examples/js/controls/OrbitControls.js
 *   THREE_DIR=$PWD/package node verificar.js ...
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [html, out] = process.argv.slice(2);
  if (!html || !out) { console.log('uso: node verificar.js <modelo-3d.html> <pasta_de_capturas>'); process.exit(1); }
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 760 } });
  if (process.env.THREE_DIR) {
    const d = process.env.THREE_DIR;
    await p.route('**/three.min.js', r => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(d, 'build/three.min.js')) }));
    await p.route('**/OrbitControls.js', r => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(d, 'examples/js/controls/OrbitControls.js')) }));
    await p.route('**fonts**', r => r.abort());
  }
  const erros = [];
  p.on('pageerror', e => erros.push(String(e)));
  p.on('console', m => { if (m.type() === 'error' && !/ERR_FAILED|ERR_TUNNEL/.test(m.text())) erros.push(m.text()); });
  await p.goto('file://' + path.resolve(html));
  await p.waitForTimeout(1500);
  const foto = async (nome, espera) => { await p.waitForTimeout(espera); await p.screenshot({ path: path.join(out, nome + '.png') }); };
  await p.click('#m-antes');  await foto('antes', 1500);
  await p.click('#m-obra');   await foto('obra', 1500);
  await p.click('#m-depois'); await foto('depois', 1500);
  await p.click('#o-rua');    await foto('rua', 4500);
  await p.click('#o-dir');    await foto('direita', 5000);
  console.log('erros:', erros.join(' | ') || 'nenhum');
  console.log('capturas em', out);
  await b.close();
})();
