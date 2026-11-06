import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";

export async function PATCH(request: Request) {
  const store=await cookies(), auth=readSession(store.get(sessionCookieName)?.value);
  if(auth?.role!== "school") return NextResponse.json({error:"Non autorisé"},{status:401});
  const b=await request.json(); const payload:any={};
  if(b.name!==undefined)payload.name=b.name;
  if(b.address!==undefined)payload.address=b.address;
  if(b.phone!==undefined)payload.phone=b.phone;
  if(b.logo!==undefined)payload.logo_url=b.logo;
  if(b.academic_year!==undefined)payload.academic_year=b.academic_year;
  const {data,error}=await supabaseServer().from("schools").update(payload).eq("id",auth.schoolId).select().single();
  if(error) return NextResponse.json({error:error.message},{status:400});return NextResponse.json(data);
}
