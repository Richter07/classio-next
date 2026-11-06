"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SuperAdminDashboard({ initialSchools }) {
  const [schools, setSchools] = useState(initialSchools);
  const [form, setForm] = useState({ name:"", code:"", password:"", location:"", phone:"" });
  const [error, setError] = useState("");
  const router = useRouter();
  async function createSchool(event) {
    event.preventDefault(); setError("");
    const response = await fetch("/api/superadmin/schools", { method:"POST", headers:{ "Content-Type":"application/json" }, body:JSON.stringify(form) });
    const school = await response.json(); if (!response.ok) { setError(school.error); return; }
    setSchools([school, ...schools]); setForm({ name:"", code:"", password:"", location:"", phone:"" });
  }
  async function toggle(school) {
    const active = !(school.subscription_status === "active" || school.active);
    const response = await fetch(`/api/superadmin/schools/${school.id}`, { method:"PATCH", headers:{ "Content-Type":"application/json" }, body:JSON.stringify({ active, subscription_status: active ? "active":"inactive" }) });
    if (response.ok) setSchools(schools.map(s => s.id === school.id ? { ...s, active, subscription_status: active ? "active":"inactive" } : s));
  }
  async function logout(){ await fetch("/api/auth/logout",{method:"POST"}); router.push("/"); }
  const active = schools.filter(s => s.subscription_status === "active" || s.active).length;
  return <main className="dashboard"><header><div><div className="eyebrow">CLASSIO</div><h1>Super-Administration</h1></div><button className="secondary" onClick={logout}>Déconnexion</button></header><section className="stats"><article><b>{schools.length}</b><span>Écoles</span></article><article><b>{active}</b><span>Abonnements actifs</span></article></section>
    <section className="panel"><h2>Créer une école</h2><form className="grid-form" onSubmit={createSchool}><input required placeholder="Nom de l’école" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><input required placeholder="Code (CLSC-ABOM-01)" value={form.code} onChange={e=>setForm({...form,code:e.target.value.toUpperCase()})}/><input required type="password" placeholder="Mot de passe école" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/><input required placeholder="Localisation" value={form.location} onChange={e=>setForm({...form,location:e.target.value})}/><input placeholder="Téléphone" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/><button className="button">Créer l’école</button></form>{error&&<p className="error">{error}</p>}</section>
    <section className="panel"><h2>Écoles Classio</h2><div className="table-wrap"><table><thead><tr><th>Nom</th><th>Code</th><th>Lieu</th><th>Téléphone</th><th>Abonnement</th><th>Action</th></tr></thead><tbody>{schools.map(s=>{const on=s.subscription_status==="active"||s.active;return <tr key={s.id}><td>{s.name}</td><td>{s.code||s.school_code}</td><td>{s.location||s.commune||"-"}</td><td>{s.phone||"-"}</td><td><span className={on?"status on":"status"}>{on?"Actif":"Inactif"}</span></td><td><button className="secondary" onClick={()=>toggle(s)}>{on?"Désactiver":"Activer"}</button></td></tr>})}</tbody></table></div></section></main>;
}
