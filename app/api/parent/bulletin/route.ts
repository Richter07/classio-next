import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";

export async function GET(request: Request) {
  const store=await cookies(), auth=readSession(store.get(sessionCookieName)?.value);
  if(auth?.role!== "parent") return NextResponse.json({error:"Non autorisé"},{status:401});
  const db=supabaseServer();
  const [{data:student},{data:school},{data:grades}]=await Promise.all([
    db.from("students").select("*").eq("id",auth.studentId).eq("school_id",auth.schoolId).single(),
    db.from("schools").select("*").eq("id",auth.schoolId).single(),
    db.from("grades").select("*").eq("student_id",auth.studentId).eq("school_id",auth.schoolId)
  ]);
  if(!student||!school) return NextResponse.json({error:"Dossier introuvable"},{status:404});
  const term=new URL(request.url).searchParams.get("term")||"T1";
  const year=school.academic_year||"2026-2027";
  const notes=(grades||[]).filter(g=>{
    const [storedTerm,storedYear]=String(g.term||"").split(":");
    return storedTerm===term && (!storedYear || storedYear===year || g.school_year===year);
  });
  const average=notes.length?notes.reduce((sum,g)=>sum+Number(g.grade||0),0)/notes.length:null;
  const appreciation=(value:number)=>value>=16?"Excellent":value>=14?"Très bien":value>=12?"Bien":value>=10?"Passable":"À renforcer";
  const logo=school.logo_url?`<img class="logo" src="${school.logo_url}" alt="Logo"/>`:"";
  const html=`<!doctype html><html><head><meta charset="utf-8"><title>Bulletin ${term}</title><style>@page{size:A4;margin:15mm}body{font-family:Arial;color:#172033}header{text-align:center}.logo{max-height:70px}table{width:100%;border-collapse:collapse;margin-top:20px}th,td{border:1px solid #cbd5e1;padding:8px;text-align:left}.summary{margin-top:20px;font-weight:bold}</style></head><body><header>${logo}<h1>${school.name||"École"}</h1><p>${school.address||school.location||""} · ${school.phone||""}</p><h2>Bulletin ${term} - Année ${year}</h2></header><h3>${student.last_name} ${student.first_name}</h3><table><thead><tr><th>Matière</th><th>Note</th><th>Appréciation</th></tr></thead><tbody>${notes.map(g=>`<tr><td>${g.subject||""}</td><td>${g.grade}/20</td><td>${appreciation(Number(g.grade))}</td></tr>`).join("")}</tbody></table><p class="summary">Moyenne globale : ${average?.toFixed(2)||"-"}/20</p><p class="summary">Décision : ${average===null?"-":average>=10?"Admis(e)":"À encourager"}</p><script>window.onload=()=>window.print()<\\/script></body></html>`;
  return new NextResponse(html,{headers:{"Content-Type":"text/html; charset=utf-8"}});
}
