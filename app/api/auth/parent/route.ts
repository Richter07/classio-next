import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase";
import { createSession, sessionCookieName } from "@/lib/session";

export async function POST(request: Request) {
  const { code } = await request.json();
  const { data } = await supabaseServer().from("students").select("id,school_id,last_name,first_name,code").ilike("code", String(code || "").trim()).limit(1);
  if (!data?.[0]) return NextResponse.json({ error: "Code élève introuvable" }, { status: 401 });
  const response = NextResponse.json({ ok: true });
  response.cookies.set(sessionCookieName, createSession({ role: "parent", studentId: data[0].id, schoolId: data[0].school_id }), { httpOnly: true, sameSite: "lax", path: "/" });
  return response;
}

