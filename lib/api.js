// Toute erreur serveur devient une réponse JSON claire (jamais une page HTML) : le navigateur peut toujours lire la réponse.
import { NextResponse } from "next/server"; import { session } from "@/lib/auth";
export const api = fn => async (req, ctx) => { try { return await fn(req, ctx); } catch (e) { console.error("API", e); return NextResponse.json({ error: "Erreur serveur. Réessayez dans un instant." }, { status: 500 }); } };
export const bad = (error, status = 400) => NextResponse.json({ error }, { status });
export const need = async role => { const s = await session(); return s && s.role === role ? s : null; };
