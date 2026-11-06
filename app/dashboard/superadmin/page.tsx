import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";
import { supabaseServer } from "@/lib/supabase";
import SuperAdminDashboard from "@/components/SuperAdminDashboard";

export default async function Page() {
  const store = await cookies();
  const session = readSession(store.get(sessionCookieName)?.value);
  if (session?.role !== "superadmin") redirect("/dashboard/superadmin/login");
  const { data } = await supabaseServer().from("schools").select("*").order("created_at", { ascending: false });
  return <SuperAdminDashboard initialSchools={data || []} />;
}

