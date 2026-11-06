// Limitation des essais ratés sur 10 minutes. Trois protections :
//  - 5 essais pour le même CODE depuis la même IP
//  - 15 essais pour le même CODE depuis n'importe quelles IP (attaque répartie)
//  - 20 essais depuis la même IP, tous codes confondus (balayage de codes)
const clean = s => String(s || "").replace(/[^A-Za-z0-9.:_-]/g, "").slice(0, 64);
export const ip = req => clean(req.headers.get("cf-connecting-ip") || (req.headers.get("x-forwarded-for") || "x").split(",")[0]);
export async function tooMany(d, a, kind, subject) {
  const sub = clean(subject), since = new Date(Date.now() - 6e5).toISOString();
  const { data } = await d.from("access_attempts").select("ip,subject").eq("kind", kind).gte("at", since).or(`ip.eq.${a},subject.eq.${sub}`);
  const rows = data || [];
  return rows.filter(r => r.ip === a && r.subject === sub).length >= 5 || rows.filter(r => r.subject === sub).length >= 15 || rows.filter(r => r.ip === a).length >= 20;
}
export const fail = (d, a, kind, subject) => d.from("access_attempts").insert({ ip: a, kind, subject: clean(subject) });
