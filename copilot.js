const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function ollama(prompt) {
  const payload = JSON.stringify({ model: 'llama3.2', prompt, stream: false });
  fs.writeFileSync('payload.json', payload);
  const cmd = `curl -s -m 180 -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d @payload.json`;
  const out = execSync(cmd, { maxBuffer: 100 * 1024 * 1024 }).toString();
  const data = JSON.parse(out);
  return data.response;
}

function scan(dir, base, out = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const e of entries) {
    if (e.name === 'node_modules' || e.name === '.next') continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) scan(full, base, out);
    else if (e.name.endsWith('.js') || e.name.endsWith('.js')) {
      out.push({ path: path.relative(base, full), content: fs.readFileSync(full, 'utf8').slice(0, 3000) });
    }
  }
  return out;
}

async function main() {
  console.log('AUDIT TOTAL EN COURS...');
  const base = path.join(process.cwd(), 'app');
  const files = scan(base, base);
  console.log(files.length + ' fichiers trouvés');
  const dump = files.map(f => `\n--- ${f.path} ---\n${f.content}`).join('\n').slice(0, 12000);
  const prompt = `Fais AUDIT TOTAL + RESTRUCTURE. Reponds UNIQUEMENT en JSON: {"analyse":"...","nouvelle_structure":["..."],"fixes":[{"path":"app/...","content":"code complet","raison":"..."}]}\n\nDump:${dump}`;
  console.log('Appel à Ollama, attends 1-3 min...');
  const text = await ollama(prompt);
  console.log('OLLAMA A REPONDU');
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) { fs.writeFileSync('AUDIT_RAPPORT.md', text); console.log('Rapport sauvegarde'); return; }
  const result = JSON.parse(match[0]);
  fs.writeFileSync('AUDIT_RAPPORT.md', result.analyse + '\n\nSTRUCTURE:\n' + (result.nouvelle_structure || []).join('\n'));
  for (const f of result.fixes || []) {
    const full = path.join(process.cwd(), f.path);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, f.content);
    console.log('Corrigé: ' + f.path);
  }
  console.log('TERMINÉ');
}
main().catch(e => console.error('ECHEC:', e.message));