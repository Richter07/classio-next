import { NextResponse } from "next/server";
import { createSession, sessionCookieName } from "@/lib/session";

export async function POST(request: Request) {
  const body = await request.json();
  if (body.email !== process.env.SUPERADMIN_EMAIL || body.password !== process.env.SUPERADMIN_PASSWORD) {
    return NextResponse.json({ error: "Identifiants super-admin incorrects" }, { status: 401 });
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set(sessionCookieName, createSession({ role: "superadmin" }), { httpOnly: true, sameSite: "lax", path: "/" });
  return response;
}

