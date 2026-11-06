import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";

export default async function ParentDashboard() {
  const store=await cookies(); const session=readSession(store.get(sessionCookieName)?.value);
  if(session?.role!== "parent") redirect("/parent");
  const db=supabaseServer();
  const [{data:student},{data:classes},{data:grades},{data:announcements},{data:school}] = await Promise.all([
    db.from("students").select("*").eq("id",session.studentId).single(),
    db.from("classes").select("*").eq("school_id",session.schoolId),
    db.from("grades").select("*").eq("student_id",session.studentId),
    db.from("announcements").select("*").eq("school_id",session.schoolId).order("date",{ascending:false}),
    db.from("schools").select("*").eq("id",session.schoolId).single()
  ]);
  if(!student) redirect("/parent");
  const cls=(classes||[]).find(c=>c.id===student.class_id);
  const year=school?.academic_year||"2026-2027";
  return <main className="dashboard"><header><div><div className="eyebrow">CLASSIO</div><h1>{student.last_name} {student.first_name}</h1></div></header><section className="panel"><h2>Informations élève</h2><p>{cls?.name||"Classe"} · Année scolaire {year}</p><p>Code élève : <b>{student.code}</b></p></section><section className="panel"><h2>Annonces de l’école</h2>{(announcements||[]).map(a=><article className="student-card" key={a.id}><b>{a.title}</b><p>{a.message}</p><small>{a.date}</small></article>)}</section><section className="panel"><h2>Notes</h2><div className="table-wrap"><table><thead><tr><th>Matière</th><th>Trimestre</th><th>Note</th></tr></thead><tbody>{(grades||[]).map(g=><tr key={g.id}><td>{g.subject}</td><td>{g.term}</td><td>{g.grade}/20</td></tr>)}</tbody></table></div>{["T1","T2","T3"].map(t=><a key={t} className="button bulletin-download" href={`/api/parent/bulletin?term=${t}`} target="_blank">Télécharger le bulletin {t} PDF</a>)}</section></main>;
}
