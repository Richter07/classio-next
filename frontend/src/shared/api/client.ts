export class ApiError extends Error {
  status: number;
  body: Record<string, unknown>;
  constructor(status: number, body: Record<string, unknown>) {
    super(ApiError.messageFrom(status, body));
    this.status = status;
    this.body = body;
  }

  static messageFrom(status: number, body: Record<string, unknown>): string {
    if (typeof body.detail === "string") return body.detail;
    for (const value of Object.values(body)) {
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
    }
    if (status === 0) return "Pas de connexion. Vérifiez votre réseau.";
    if (status >= 500) return "Le serveur a rencontré un problème. Réessayez.";
    return "Une erreur est survenue.";
  }
}

function cookie(name: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${name}=`))
    ?.split("=")[1];
}

let csrfReady: Promise<unknown> | null = null;
export function ensureCsrf() {
  csrfReady ??= fetch("/api/v1/auth/csrf/", { credentials: "same-origin" });
  return csrfReady;
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; form?: FormData } = {},
): Promise<T> {
  const method = options.method ?? (options.body || options.form ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    await ensureCsrf();
    headers["X-CSRFToken"] = cookie("csrftoken") ?? "";
  }
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(`/api/v1/${path}`, { method, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, {});
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

/** Lien direct vers un fichier servi par l'API (PDF, Excel) : le cookie de session suffit. */
export const fileUrl = (path: string) => `/api/v1/${path}`;
