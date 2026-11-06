import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase";
import crypto from "crypto";

export async function POST(request: Request) {
  const {email,password}=await request.json();
  if(!email&&!password)return NextResponse.json({error:"Email requis"},{status:400});
  if(password){
    const {data}=await supabaseServer().from("schools").select("id,email").ilike("email",String(email||"").trim()).limit(1);
    if(!data?.[0])return NextResponse.json({error:"Compte école introuvable"},{status:404});
    const {error}=await supabaseServer().from("schools").update({password}).eq("id",data[0].id);
    if(error)return NextResponse.json({error:error.message},{status:400});
    return NextResponse.json({ok:true});
  }
  const token=crypto.randomBytes(24).toString("hex");
  return NextResponse.json({ok:true,preview_token:process.env.NODE_ENV==="development"?token:undefined});
}
