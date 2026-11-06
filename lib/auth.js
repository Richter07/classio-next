// Sessions signées (cookie "cs") et mots de passe, avec l'API Web Crypto : fonctionne sur Cloudflare Workers ET sur Vercel.
import { cookies } from "next/headers";

const encoder = new TextEncoder();
const toHex = (bytes) => [...new Uint8Array(bytes)].map((value) => value.toString(16).padStart(2, "0")).join("");

function secret() {
  const value = process.env.SESSION_SECRET;
  if (!value || value.length < 32) throw new Error("SESSION_SECRET must contain at least 32 characters");
  return value;
}

async function sign(value) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret()), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return toHex(await crypto.subtle.sign("HMAC", key, encoder.encode(value)));
}

export const same = (first, second) => {
  const a = String(first);
  const b = String(second);
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i += 1) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
};

export async function session() {
  const cookieStore = await cookies();
  const cookie = cookieStore.get("cs")?.value;
  if (!cookie) return null;
  const separator = cookie.lastIndexOf(".");
  if (separator < 1) return null;
  const value = cookie.slice(0, separator);
  const signature = cookie.slice(separator + 1);
  if (!same(signature, await sign(value))) return null;
  try {
    const decoded = JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
    return decoded.exp > Date.now() ? decoded : null;
  } catch {
    return null;
  }
}

export async function setSession(response, data, hours = 8) {
  const value = Buffer.from(JSON.stringify({ ...data, exp: Date.now() + hours * 60 * 60 * 1000 })).toString("base64url");
  response.cookies.set("cs", `${value}.${await sign(value)}`, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: hours * 60 * 60,
  });
  return response;
}

export async function clearSession(response) {
  response.cookies.set("cs", "", { httpOnly: true, path: "/", maxAge: 0 });
  return response;
}

export async function hashPw(password, salt = toHex(crypto.getRandomValues(new Uint8Array(16)))) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: encoder.encode(salt), iterations: 100000 }, key, 256);
  return `${salt}:${toHex(bits)}`;
}

export async function checkPw(password, stored) {
  const salt = String(stored || "").split(":")[0];
  return !!salt && same(await hashPw(password, salt), stored);
}

export function randomPw() {
  const alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return [...crypto.getRandomValues(new Uint8Array(10))].map((value) => alphabet[value % alphabet.length]).join("");
}
