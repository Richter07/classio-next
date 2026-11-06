"use client";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function SchoolLogin() {
  const [code,setCode]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState(""); const router=useRouter();
  async function submit(event: FormEvent){ event.preventDefault(); setError(""); const response=await fetch("/api/auth/school",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code,password})}); if(!response.ok){setError((await response.json()).error);return;} router.push("/dashboard/ecole"); }
  return <main className="login"><form className="login-card" onSubmit={submit}><h1>Connexion École Classio</h1><input className="field" placeholder="Code école" value={code} onChange={e=>setCode(e.target.value)} required /><input className="field" type="password" placeholder="Mot de passe école" value={password} onChange={e=>setPassword(e.target.value)} required /><button className="button">Ouvrir mon école</button>{error && <p className="error">{error}</p>}<a href="/mot-de-passe-oublie/ecole">Mot de passe oublié</a></form></main>;
}
