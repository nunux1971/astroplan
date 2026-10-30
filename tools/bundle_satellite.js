// Regroupe le sous-ensemble SGP4 de satellite.js (sources TypeScript) en src/vendor/satellite.js.
// Usage : node tools/bundle_satellite.js chemin/vers/satellite-js/src astroplan-entry.ts > src/vendor/satellite.js
// avec astroplan-entry.ts :
//   export { twoline2satrec } from './io.js';
//   export { propagate } from './propagation.js';
//   export { gstime } from './propagation/gstime.js';
//   export { eciToEcf, eciToGeodetic, ecfToLookAngles, degreesLat, degreesLong } from './transforms.js';
//   export { sgp4 } from './propagation/sgp4.js';
// Demande Node 22 ou plus (suppression des types TypeScript intégrée).
const fs = require('fs'), path = require('path'), { stripTypeScriptTypes } = require('node:module');
const root = process.argv[2], entries = process.argv.slice(3);
const mods = new Map(); const order = [];
function resolve(from, spec) { let p = path.resolve(path.dirname(from), spec.replace(/\.js$/, '.ts')); if (!fs.existsSync(p) && fs.existsSync(p.replace(/\.ts$/, '/index.ts'))) p = p.replace(/\.ts$/, '/index.ts'); return p; }
function load(file) {
  if (mods.has(file)) return; mods.set(file, null);
  let src = stripTypeScriptTypes(fs.readFileSync(file, 'utf8'), { mode: 'transform' });
  const deps = []; const tail = [];
  // import { a, b as c } from './x.js';  (multi-ligne)
  src = src.replace(/import\s*\{([^}]*)\}\s*from\s*['"]([^'"]+)['"];?/g, (m, names, spec) => {
    const f = resolve(file, spec); deps.push(f);
    const parts = names.split(',').map(s => s.trim()).filter(Boolean).filter(s => !s.startsWith('type '));
    if (!parts.length) return '';
    return `const {${parts.map(s => s.replace(/\s+as\s+/, ': ')).join(', ')}} = __req(${JSON.stringify(f)});`;
  });
  src = src.replace(/import\s+\*\s+as\s+(\w+)\s+from\s*['"]([^'"]+)['"];?/g, (m, n, spec) => { const f = resolve(file, spec); deps.push(f); return `const ${n} = __req(${JSON.stringify(f)});`; });
  src = src.replace(/export\s*\{([^}]*)\}\s*from\s*['"]([^'"]+)['"];?/g, (m, names, spec) => {
    const f = resolve(file, spec); deps.push(f);
    return names.split(',').map(s => s.trim()).filter(Boolean).filter(s => !s.startsWith('type ')).map(s => { const [a, b] = s.split(/\s+as\s+/); return `Object.defineProperty(exports, ${JSON.stringify(b || a)}, {enumerable:true, get: () => __req(${JSON.stringify(f)})[${JSON.stringify(a)}]});`; }).join('\n');
  });
  src = src.replace(/export\s*\*\s*from\s*['"]([^'"]+)['"];?/g, (m, spec) => { const f = resolve(file, spec); deps.push(f); return `Object.assign(exports, __req(${JSON.stringify(f)}));`; });
  src = src.replace(/export\s*\{([^}]*)\};?/g, (m, names) => { names.split(',').map(s => s.trim()).filter(Boolean).forEach(s => { const [a, b] = s.split(/\s+as\s+/); tail.push(`exports.${b || a} = ${a};`); }); return ''; });
  src = src.replace(/export\s+(async\s+)?(function\*?|class|const|let|var)\s+(\w+)/g, (m, as, kw, name) => { tail.push(`exports.${name} = ${name};`); return `${as || ''}${kw} ${name}`; });
  src = src.replace(/export\s+default\s+/g, 'exports.default = ');
  if (/\bimport\b[^(]|\bexport\b/.test(src.replace(/\/\/.*|\/\*[\s\S]*?\*\//g, ''))) console.error('reste import/export dans', file);
  mods.set(file, `${src}\n${tail.join('\n')}`);
  deps.forEach(load); order.push(file);
}
entries.forEach(e => load(path.resolve(root, e)));
let out = `/* satellite.js (MIT, © 2013 Shashwat Kandadai, UCSC) — sous-ensemble SGP4 regroupé pour AstroPlan */\nconst satellite = (() => {\nconst __defs = {}, __cache = {};\nfunction __req(f) { if (__cache[f]) return __cache[f]; const exports = __cache[f] = {}; __defs[f](exports); return exports; }\n`;
for (const f of order) out += `__defs[${JSON.stringify(f)}] = function (exports) {\n${mods.get(f)}\n};\n`;
out += `return ${entries.map(e => `__req(${JSON.stringify(path.resolve(root, e))})`).join(', ')};\n})();\n`;
// noms de fichiers absolus -> courts
out = out.split(path.resolve(root) + '/').join('');
process.stdout.write(out);
