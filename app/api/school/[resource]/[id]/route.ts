import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";

const allowed = ["students","classes","matieres","grades","announcements"];
export async function PATCH(request: Request, { params }: { params: Promise<{ resource:string; id:string }> }) {
  const { resource,id } = await params; const store=await cookies(); const auth=readSession(store.get(sessionCookieName)?.value);
  if(auth?.role!== "school" || !allowed.includes(resource)) return NextResponse.json({error:"Non autorisé"},{status:401});
  const body=await request.json();
  const payload={...body}; delete payload.gender;
  if(resource==="students" && body.gender) payload.photo_url=`classio_gender:${body.gender}`;
  if(resource==="grades" && body.school_year){payload.term=`${body.term}:${body.school_year}`;delete payload.school_year;}
  const {data,error}=await supabaseServer().from(resource).update(payload).eq("id",id).eq("school_id",auth.schoolId).select().single();
  if(error) return NextResponse.json({error:error.message},{status:400}); return NextResponse.json(data);
}
export async function DELETE(request: Request, { params }: { params: Promise<{ resource:string; id:string }> }) {
  const { resource,id } = await params; const store=await cookies(); const auth=readSession(store.get(sessionCookieName)?.value);
  if(auth?.role!== "school" || !allowed.includes(resource)) return NextResponse.json({error:"Non autorisé"},{status:401});
  const {error}=await supabaseServer().from(resource).delete().eq("id",id).eq("school_id",auth.schoolId);
  if(error) return NextResponse.json({error:error.message},{status:400}); return NextResponse.json({ok:true});
}
