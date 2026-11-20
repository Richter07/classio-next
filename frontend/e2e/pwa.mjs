// Classio, vérification de l'application installable (PWA) sur la version de production.
//
//   npm run build && npm run e2e:pwa      (l'API de développement doit tourner sur le port 8000)
//
// Ce que l'on vérifie :
// - le manifeste et le service worker ;
// - la carte « Installer Classio » selon le téléphone : Android, iPhone, WhatsApp, déjà installée ;
// - « Plus tard » est retenu ;
// - le bandeau « nouvelle version » après un déploiement ;
// - le bandeau hors connexion du parent ;
// - aucune réponse de l'API (données d'élèves) dans le cache du téléphone.
import { spawn } from "node:child_process";
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const PORT = 4173;
const BASE = `http://localhost:${PORT}`;
const SHOTS = process.env.E2E_SHOTS ?? "e2e/captures";
const PASSWORD = "classio-demo-2026";
const UA = {
  android:
    "Mozilla/5.0 (Linux; Android 13; SM-A135F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
  iphone:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  inApp:
    "Mozilla/5.0 (Linux; Android 13; SM-A135F; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.0.0 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/450.0.0.0;]",
};

let failures = 0;
async function step(name, fn) {
  try {
    await fn();
    console.log(`✓ ${name}`);
  } catch (error) {
    failures++;
    console.log(`✗ ${name}\n    ${String(error.message ?? error).split("\n")[0]}`);
  }
}
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

async function preview() {
  const server = spawn("node_modules/.bin/vite", ["preview", "--port", String(PORT), "--strictPort"], { stdio: "ignore" });
  let exited = null;
  server.on("exit", (code) => (exited = code));
  for (let i = 0; i < 60; i++) {
    if (exited !== null) throw new Error(`vite preview arrêté (${exited})`);
    if (await fetch(BASE).then((r) => r.ok, () => false)) return server;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("vite preview ne répond pas");
}
const stop = (server) =>
  new Promise((resolve) => {
    if (server.exitCode !== null) return resolve();
    server.once("exit", resolve);
    server.kill();
  });

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM || undefined });
const device = { viewport: { width: 360, height: 760 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-FR" };
const errors = [];
async function open(ctx, path = "/") {
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(e.message));
  await p.goto(BASE + path);
  return p;
}
const swReady = (p) => p.evaluate(() => navigator.serviceWorker.ready.then(() => true));

let server = await preview();

// Une seule connexion, réutilisée par chaque « téléphone » (la connexion est limitée en nombre d'essais).
const login = await browser.newContext({ ...device, userAgent: UA.android });
const lp = await open(login);
await lp.getByLabel("Numéro de téléphone").fill("97 00 00 01");
await lp.getByLabel("Mot de passe").fill(PASSWORD);
await lp.getByRole("button", { name: "Me connecter" }).click();
await lp.waitForURL("**/parent");
const session = await login.storageState();
await login.close();
const phone = (userAgent, extra = {}) => browser.newContext({ ...device, userAgent, storageState: session, ...extra });

await step("Manifeste : installable (nom, icônes, plein écran)", async () => {
  const ctx = await phone(UA.android);
  const p = await open(ctx);
  const href = await p.locator('link[rel="manifest"]').getAttribute("href");
  const manifest = await (await ctx.request.get(new URL(href, BASE).href)).json();
  assert(manifest.name === "Classio" && manifest.display === "standalone", "nom ou mode d'affichage");
  assert(manifest.id === "/" && manifest.scope === "/" && manifest.start_url === "/", "id, scope, start_url");
  const sizes = manifest.icons.map((i) => `${i.sizes}${i.purpose ? `-${i.purpose}` : ""}`);
  assert(sizes.includes("192x192") && sizes.includes("512x512") && sizes.includes("512x512-maskable"), `icônes : ${sizes}`);
  for (const icon of manifest.icons) assert((await ctx.request.get(BASE + icon.src)).ok(), `icône absente : ${icon.src}`);
  assert(await swReady(p), "service worker non actif");
  await ctx.close();
});

await step("Android (Chrome propose l'installation) : bouton Installer", async () => {
  const ctx = await phone(UA.android);
  const p = await open(ctx, "/parent");
  await p.locator(".child-card").first().waitFor();
  // Chrome n'envoie pas cet événement en test automatisé : on le reproduit à l'identique.
  await p.evaluate(() => {
    const event = new Event("beforeinstallprompt");
    event.prompt = async () => (window.__prompted = true);
    event.userChoice = Promise.resolve({ outcome: "accepted" });
    window.dispatchEvent(event);
  });
  await p.getByRole("button", { name: "Installer" }).waitFor();
  await p.screenshot({ path: `${SHOTS}/pwa-android.png` });
  await p.getByRole("button", { name: "Installer" }).click();
  await p.waitForFunction(() => window.__prompted === true);
  await p.locator(".install-card").waitFor({ state: "detached" });
  await ctx.close();
});

await step("Android sans proposition : marche à suivre par le menu ⋮", async () => {
  const ctx = await phone(UA.android);
  const p = await open(ctx, "/parent");
  await p.getByText("« Installer l'application »").waitFor();
  await ctx.close();
});

await step("iPhone : marche à suivre par Partager", async () => {
  const ctx = await phone(UA.iphone);
  const p = await open(ctx, "/parent");
  await p.getByText("« Sur l'écran d'accueil »").waitFor();
  await p.screenshot({ path: `${SHOTS}/pwa-iphone.png` });
  await ctx.close();
});

await step("Ouvert depuis WhatsApp ou Facebook : ouvrir dans le navigateur", async () => {
  const ctx = await phone(UA.inApp);
  const p = await open(ctx, "/parent");
  await p.getByText("« Ouvrir dans le navigateur »").waitFor();
  await ctx.close();
});

await step("Déjà installée : aucune invitation", async () => {
  const ctx = await phone(UA.android);
  await ctx.addInitScript(() => {
    const original = window.matchMedia.bind(window);
    window.matchMedia = (query) =>
      query.includes("display-mode: standalone") ? { matches: true, media: query, addEventListener() {}, removeEventListener() {} } : original(query);
  });
  const p = await open(ctx, "/parent");
  await p.locator(".child-card").first().waitFor();
  assert((await p.locator(".install-card").count()) === 0, "la carte est affichée");
  await ctx.close();
});

await step("« Plus tard » est retenu ; la page Mon compte la propose toujours", async () => {
  const ctx = await phone(UA.iphone);
  const p = await open(ctx, "/parent");
  await p.getByRole("button", { name: "Plus tard" }).click();
  await p.reload();
  await p.locator(".child-card").first().waitFor();
  assert((await p.locator(".install-card").count()) === 0, "la carte est revenue");
  await p.goto(`${BASE}/parent/compte`);
  await p.locator(".install-card").waitFor();
  assert((await p.getByRole("button", { name: "Plus tard" }).count()) === 0, "bouton Plus tard sur Mon compte");
  await ctx.close();
});

await step("Hors connexion : bandeau, la page reste affichée", async () => {
  const ctx = await phone(UA.android);
  const p = await open(ctx, "/parent");
  await p.locator(".child-card").first().waitFor();
  await ctx.setOffline(true);
  await p.getByText("Pas de connexion").waitFor();
  assert(await p.locator(".child-card").first().isVisible(), "les enfants ont disparu");
  await ctx.setOffline(false);
  await p.locator(".offline-banner").waitFor({ state: "detached" });
  await ctx.close();
});

await step("Cache du téléphone : aucune réponse de l'API", async () => {
  const ctx = await phone(UA.android);
  const p = await open(ctx, "/parent");
  await swReady(p);
  await p.locator(".child-card").first().click();
  await p.getByText("Bulletin publié par l'école").waitFor();
  const cached = await p.evaluate(async () => {
    const urls = [];
    for (const name of await caches.keys()) for (const req of await (await caches.open(name)).keys()) urls.push(req.url);
    return urls;
  });
  assert(cached.length > 0, "rien en cache : l'application ne s'ouvrira pas hors connexion");
  const api = cached.filter((url) => new URL(url).pathname.startsWith("/api/"));
  assert(api.length === 0, `réponses de l'API en cache : ${api.join(", ")}`);
  await ctx.close();
});

// Deux cas : la visite habituelle (la page est pilotée par le service worker) et la toute
// première visite (elle ne l'est pas encore).
for (const [label, controlled] of [["visite habituelle", true], ["première visite", false]]) {
  await step(`Nouvelle version déployée (${label}) : bandeau, puis mise à jour à la demande`, async () => {
    const ctx = await phone(UA.android);
    const p = await open(ctx, "/parent");
    await swReady(p);
    if (controlled) await p.reload();
    await p.locator(".child-card").first().waitFor();
    assert((await p.evaluate(() => !!navigator.serviceWorker.controller)) === controlled, "état du service worker inattendu");
    // Déploiement simulé : le service worker publié change.
    await stop(server);
    const sw = "dist/sw.js";
    const original = readFileSync(sw, "utf8");
    appendFileSync(sw, `\n// déploiement ${Date.now()}\n`);
    try {
      server = await preview();
      await p.evaluate(async () => (await navigator.serviceWorker.getRegistration()).update());
      await p.getByText("Une nouvelle version de Classio est disponible.").waitFor({ timeout: 15000 });
      if (controlled) await p.screenshot({ path: `${SHOTS}/pwa-mise-a-jour.png` });
      await Promise.all([p.waitForEvent("load"), p.getByRole("button", { name: "Mettre à jour" }).click()]);
      await p.locator(".child-card").first().waitFor();
      assert((await p.locator(".update-banner").count()) === 0, "le bandeau est resté");
    } finally {
      writeFileSync(sw, original);
    }
    await ctx.close();
  });
}

await browser.close();
await stop(server);
console.log(`\nErreurs JavaScript : ${errors.length ? errors.join(" | ") : "aucune"}`);
console.log(`${failures ? `${failures} en échec` : "Tout est conforme"}.`);
process.exit(failures || errors.length ? 1 : 0);
