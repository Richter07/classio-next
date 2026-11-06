import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";

async function session() {
  const store = await cookies();
  return readSession(store.get(sessionCookieName)?.value);
}
export async function GET() {
  const auth = await session();
  if (auth?.role !== "superadmin") return NextResponse.json({ error: "Non autorisé" }, { status: 401 });
  const { data, error } = await supabaseServer().from("schools").select("*").order("created_at", { ascending: false });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data || []);
}
export async function POST(request: Request) {
  const auth = await session();
  if (auth?.role !== "superadmin") return NextResponse.json({ error: "Non autorisé" }, { status: 401 });
  const body = await request.json();
  const { data, error } = await supabaseServer().from("schools").insert({
    name: body.name, code: String(body.code).toUpperCase(), school_code: String(body.code).toUpperCase(),
    password: body.password, location: body.location, phone: body.phone, commune: body.location,
    subscription_status: body.subscription_status || "active", active: true, plan: "essentiel"
  }).select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json(data);
}
