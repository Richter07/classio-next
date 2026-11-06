import crypto from "crypto";

const COOKIE = "classio_session";

export function createSession(payload) {
  const body = Buffer.from(JSON.stringify({ ...payload, exp: Date.now() + 12 * 60 * 60 * 1000 })).toString("base64url");
  const sig = crypto.createHmac("sha256", process.env.SESSION_SECRET || "classio-session-secret").update(body).digest("base64url");
  return `${body}.${sig}`;
}

export function readSession(token) {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const sig = crypto.createHmac("sha256", process.env.SESSION_SECRET || "classio-session-secret").update(parts[0]).digest("base64url");
  if (!crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(parts[1]))) return null;
  try {
    const payload = JSON.parse(Buffer.from(parts[0], "base64url").toString());
    return payload.exp > Date.now() ? payload : null;
  } catch {
    return null;
  }
}

export const sessionCookieName = COOKIE;

