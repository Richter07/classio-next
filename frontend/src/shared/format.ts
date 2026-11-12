const number = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const dateFormat = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const longDate = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" });

export const fmt = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : number.format(value);

export const fmtDate = (value: string | null | undefined) =>
  value ? dateFormat.format(new Date(value)) : "";

export const today = () => longDate.format(new Date());

const fullDate = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });
export const fmtFullDate = (value: string) => fullDate.format(new Date(value));

export function relative(value: string): string {
  const days = Math.round((Date.now() - new Date(value).getTime()) / 86_400_000);
  if (days <= 0) return "aujourd'hui";
  if (days === 1) return "hier";
  if (days < 7) return `il y a ${days} jours`;
  return `le ${fmtDate(value)}`;
}

export const initials = (first: string, last: string) =>
  `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();

/** Affiche un numéro E.164 béninois comme on l'écrit : 01 97 00 00 01. */
export function phone(value: string): string {
  const local = value.replace(/^\+229/, "");
  return local.replace(/(\d{2})(?=\d)/g, "$1 ").trim();
}

export function plural(count: number, one: string, many = `${one}s`) {
  return `${count} ${count > 1 ? many : one}`;
}

/** Nom de période assez court pour trois onglets sur un écran de 360 px. */
export const shortPeriod = (name: string) =>
  name.replace(/^Trimestre\s*/i, "Trim. ").replace(/^Semestre\s*/i, "Sem. ");
