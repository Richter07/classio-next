import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase";
import { createSession, sessionCookieName } from "@/lib/session";

export async function POST(request: Request) {
  const { code, password } = await request.json();
  const db = supabaseServer();
  let result = await db.from("schools").select("*").ilike("code", String(code || "").trim()).limit(1);
  if (!result.data?.length) result = await db.from("schools").select("*").ilike("school_code", String(code || "").trim()).limit(1);
  const school = result.data?.[0];
  if (!school || (school.password !== password && password !== process.env.NEXT_PUBLIC_ADMIN_PASSWORD)) {
    return NextResponse.json({ error: "Code ou mot de passe école incorrect" }, { status: 401 });
  }
  if (school.subscription_status !== "active" && school.active !== true) {
    return NextResponse.json({ error: "Abonnement école inactif" }, { status: 403 });
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set(sessionCookieName, createSession({ role: "school", schoolId: school.id }), { httpOnly: true, sameSite: "lax", path: "/" });
  return response;
}

