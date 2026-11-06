'use client';
import { useState } from 'react';

export default function CopilotCoder() {
  const [prompt, setPrompt] = useState('');
  const [filePath, setFilePath] = useState('dashboard/test/page.js');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    const res = await fetch('/api/copilot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'generate', prompt })
    });
    const data = await res.json();
    setCode(data.code);
    setLoading(false);
  };

  const writeFile = async () => {
    await fetch('/api/copilot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'write', filePath, prompt: code })
    });
    alert('Fichier créé : ' + filePath);
  };

  return (
    <div style={{ position: 'fixed', bottom: 20, left: 20, width: 450, background: '#0f172a', color: 'white', padding: 16, borderRadius: 16, zIndex: 9999 }}>
      <h3 style={{ margin: 0, marginBottom: 8 }}>Copilote Codeur</h3>
      <input value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Ex: crée une page liste des élèves avec Supabase" style={{ width: '100%', padding: 8, borderRadius: 8, marginBottom: 8 }} />
      <input value={filePath} onChange={e => setFilePath(e.target.value)} placeholder="Chemin: dashboard/ecole/page.js" style={{ width: '100%', padding: 8, borderRadius: 8, marginBottom: 8 }} />
      <button onClick={generate} disabled={loading} style={{ width: '100%', padding: 10, background: '#4f46e5', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer' }}>
        {loading ? 'Il code...' : 'Générer le code'}
      </button>
      {code && (
        <>
          <pre style={{ background: '#1e293b', padding: 10, borderRadius: 8, maxHeight: 200, overflow: 'auto', marginTop: 10, fontSize: 12 }}>{code}</pre>
          <button onClick={writeFile} style={{ width: '100%', marginTop: 8, padding: 10, background: '#16a34a', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer' }}>
            Écrire ce fichier à ma place
          </button>
        </>
      )}
    </div>
  );
}