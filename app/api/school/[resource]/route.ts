import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";

const allowed = ["students","classes","matieres","grades","announcements"];

export async function GET(request: Request, { params }: { params: Promise<{ resource: string }> }) {
  const { resource } = await params; const store = await cookies(); const auth = readSession(store.get(sessionCookieName)?.value);
  if (auth?.role !== "school" || !allowed.includes(resource)) return NextResponse.json({ error:"Non autorisé" }, { status:401 });
  const url = new URL(request.url); const db = supabaseServer();
  let query = db.from(resource).select("*").eq("school_id", auth.schoolId).limit(500);
  const classId = url.searchParams.get("class_id"); if (classId) query = query.eq("class_id", classId);
  const { data, error } = await query;
  if (error) return NextResponse.json({ error:error.message }, { status:400 });
  return NextResponse.json(data || []);
}
export async function POST(request: Request, { params }: { params: Promise<{ resource: string }> }) {
  const { resource } = await params; const store = await cookies(); const auth = readSession(store.get(sessionCookieName)?.value);
  if (auth?.role !== "school" || !allowed.includes(resource)) return NextResponse.json({ error:"Non autorisé" }, { status:401 });
  const body = await request.json();
  let payload = { ...body, school_id: auth.schoolId };
  if (resource === "grades" && body.school_year) {
    payload.term = `${body.term}:${body.school_year}`;
    delete payload.school_year;
  }
  if (resource === "students" && body.gender) {
    payload.photo_url = `classio_gender:${body.gender}`;
    delete payload.gender;
  }
  const { data, error } = await supabaseServer().from(resource).insert(payload).select().single();
  if (error) return NextResponse.json({ error:error.message }, { status:400 });
  return NextResponse.json(data);
}
