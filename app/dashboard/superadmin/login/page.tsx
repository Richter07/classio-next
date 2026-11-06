"use client";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function SuperAdminLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();
  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    const response = await fetch("/api/auth/superadmin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
    if (!response.ok) { setError((await response.json()).error); return; }
    router.push("/dashboard/superadmin");
  }
  return <main className="login"><form className="login-card" onSubmit={submit}><h1>Classio Super-Admin</h1><input className="field" type="email" placeholder="Adresse e-mail" value={email} onChange={e=>setEmail(e.target.value)} required /><input className="field" type="password" placeholder="Mot de passe" value={password} onChange={e=>setPassword(e.target.value)} required /><button className="button">Se connecter</button>{error && <p className="error">{error}</p>}<a href="/mot-de-passe-oublie/superadmin">Mot de passe oublié</a></form></main>;
}
