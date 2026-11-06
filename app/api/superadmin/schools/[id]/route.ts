import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const store = await cookies(); const auth = readSession(store.get(sessionCookieName)?.value);
  if (auth?.role !== "superadmin") return NextResponse.json({ error:"Non autorisé" }, { status:401 });
  const { id } = await params; const body = await request.json();
  const { data, error } = await supabaseServer().from("schools").update(body).eq("id", id).select().single();
  if (error) return NextResponse.json({ error:error.message }, { status:400 });
  return NextResponse.json(data);
}
