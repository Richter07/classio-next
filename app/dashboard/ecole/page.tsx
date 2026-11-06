import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";
import SchoolDashboard from "@/components/SchoolDashboard";

export default async function Page() {
  const store = await cookies(); const session = readSession(store.get(sessionCookieName)?.value);
  if (session?.role !== "school") redirect("/dashboard/ecole/login");
  const db = supabaseServer();
  const { data: school } = await db.from("schools").select("*").eq("id", session.schoolId).single();
  if (!school) redirect("/dashboard/ecole/login");
  const [students, classes, matieres, grades, announcements] = await Promise.all([
    db.from("students").select("*").eq("school_id", school.id),
    db.from("classes").select("*").eq("school_id", school.id),
    db.from("matieres").select("*").eq("school_id", school.id),
    db.from("grades").select("*").eq("school_id", school.id),
    db.from("announcements").select("*").eq("school_id", school.id).order("date", {ascending:false})
  ]);
  const studentRows=(students.data||[]).map(student=>({...student,gender:student.photo_url?.startsWith("classio_gender:")?student.photo_url.slice(15):student.gender}));
  const gradeRows=(grades.data||[]).map(grade=>{const [term,schoolYear]=String(grade.term||"").split(":");return {...grade,term:schoolYear?term:grade.term,school_year:schoolYear||school.academic_year||"2026-2027"}});
  return <SchoolDashboard school={school} initial={{students:studentRows,classes:classes.data||[],matieres:matieres.data||[],grades:gradeRows,announcements:announcements.data||[]}} />;
}
