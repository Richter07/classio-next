"use client";
import { FormEvent, use, useState } from "react";

export default function PasswordRecovery({params}:{params:Promise<{role:string}>}){
  const resolved=use(params);
  const [email,setEmail]=useState(""),[password,setPassword]=useState(""),[sent,setSent]=useState(false),[done,setDone]=useState(false),[error,setError]=useState("");
  async function request(e:FormEvent){e.preventDefault();setError("");const r=await fetch("/api/auth/password-reset",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email})});setSent(r.ok);}
  async function reset(e:FormEvent){e.preventDefault();const r=await fetch("/api/auth/password-reset",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});if(r.ok)setDone(true);else setError((await r.json()).error);}
  return <main className="login">{done?<section className="login-card"><h1>Mot de passe modifié</h1><a href={resolved.role==="superadmin"?"/dashboard/superadmin/login":"/dashboard/ecole/login"}>Se connecter</a></section>:<form className="login-card" onSubmit={sent?reset:request}><h1>Mot de passe oublié</h1>{sent?<><p>Créez votre nouveau mot de passe.</p><input className="field" type="password" required minLength={6} value={password} onChange={e=>setPassword(e.target.value)}/><button className="button">Modifier le mot de passe</button></>:<><input className="field" type="email" required placeholder="Adresse e-mail" value={email} onChange={e=>setEmail(e.target.value)}/><button className="button">Continuer</button></>}<p className="error">{error}</p></form>}</main>;
}
