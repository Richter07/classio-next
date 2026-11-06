import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase";

export async function POST(request: Request) {
  const b=await request.json();
  const {data}=await supabaseServer().from("students").select("code,last_name,first_name,birth_date").ilike("last_name",String(b.last_name||"").trim()).ilike("first_name",String(b.first_name||"").trim()).eq("birth_date",b.birth_date).limit(1);
  if(!data?.[0])return NextResponse.json({error:"Aucun élève trouvé, vérifiez les informations ou contactez l’école."},{status:404});
  return NextResponse.json({code:data[0].code});
}
