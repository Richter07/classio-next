import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { readSession, sessionCookieName } from "@/lib/session";

export default async function DocumentsPage() {
  const store=await cookies();
  if(readSession(store.get(sessionCookieName)?.value)?.role!== "school") redirect("/dashboard/ecole/login");
  redirect("/dashboard/ecole");
}
