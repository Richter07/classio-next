// Parcours de bout en bout, joué comme un vrai utilisateur, sur les quatre rôles.
//
//   ./dev.sh reset && ./dev.sh       (dans un terminal)
//   npm run e2e                      (dans frontend/, dans un autre terminal)
//
// Téléphone d'entrée de gamme (360 px) pour les parents, les enseignants et le secrétariat,
// ordinateur pour la direction. À chaque écran : capture dans e2e/captures/, contrôle qu'aucun
// élément ne dépasse la largeur de l'écran, et relevé des erreurs JavaScript.
import { mkdirSync, readFileSync } from "node:fs";
import { chromium } from "playwright";

const BASE = process.env.E2E_BASE ?? "http://localhost:5173";
const PASSWORD = "classio-demo-2026";
const SCHOOL = "ceg-les-pylones";
const SHOTS = new URL("./captures/", import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

const results = [];
const errors = [];
const ok = (name, detail = "") => results.push(`✓ ${name}${detail ? ` — ${detail}` : ""}`);
const fail = (name, error) => results.push(`✗ ${name} — ${error}`);

async function step(name, fn) {
  try {
    await fn();
    ok(name);
  } catch (e) {
    fail(name, e.message.split("\n").slice(0, 4).join(" "));
  }
}

async function check(page, name) {
  const width = page.viewportSize().width;
  await page.waitForLoadState("networkidle").catch(() => {});
  // En mode mobile, Chromium élargit la fenêtre pour faire tenir le contenu : on compare donc
  // à la largeur réelle de l'écran, et on nomme l'élément fautif.
  const overflow = await page.evaluate((w) => {
    const extra = document.documentElement.scrollWidth - w;
    if (extra <= 1) return null;
    const culprit = [...document.querySelectorAll("body *")].find(
      (el) => el.getBoundingClientRect().right > w + 1 && getComputedStyle(el).position !== "fixed",
    );
    return `${extra}px de trop (${culprit ? `${culprit.tagName.toLowerCase()}.${culprit.className}` : "?"})`;
  }, width);
  await page.screenshot({ path: `${SHOTS}${name}.png`, fullPage: true });
  if (overflow) fail(`${name} : défilement horizontal`, overflow);
}

const browser = await chromium.launch();
const phone = { viewport: { width: 360, height: 760 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-FR" };
const desktop = { viewport: { width: 1280, height: 860 }, locale: "fr-FR" };

async function context(options) {
  const ctx = await browser.newContext({ ...options, acceptDownloads: true });
  // Le serveur de développement compile chaque page à sa première ouverture : marge confortable.
  ctx.setDefaultTimeout(20_000);
  return ctx;
}
async function page(ctx, who) {
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(`${who} : ${e.message}`));
  p.on("console", (m) => m.type() === "error" && !m.text().includes("Failed to load resource") && errors.push(`${who} : ${m.text()}`));
  return p;
}
async function download(page, trigger, timeout = 120_000) {
  const started = Date.now();
  const [file] = await Promise.all([page.waitForEvent("download", { timeout }), trigger()]);
  const head = readFileSync(await file.path()).subarray(0, 4).toString();
  return { name: file.suggestedFilename(), head, seconds: ((Date.now() - started) / 1000).toFixed(1) };
}
async function staffLogin(p, number) {
  await p.goto(`${BASE}/ecole/connexion`);
  await p.getByLabel("Code de l'école").fill(SCHOOL);
  await p.getByLabel("Numéro de téléphone").fill(number);
  await p.getByLabel("Mot de passe").fill(PASSWORD);
  await p.getByRole("button", { name: "Se connecter" }).click();
  await p.waitForURL("**/ecole");
}

// ---------------------------------------------------------------- Parent avec un compte
const parentCtx = await context(phone);
const parent = await page(parentCtx, "parent");

await step("Parent : écran de connexion", async () => {
  await parent.goto(BASE);
  await parent.getByRole("heading", { name: "Suivez les notes de vos enfants" }).waitFor();
  await check(parent, "01-parent-connexion");
});
await step("Parent : mauvais mot de passe refusé", async () => {
  await parent.getByLabel("Numéro de téléphone").fill("97 00 00 01");
  await parent.getByLabel("Mot de passe").fill("pas-le-bon");
  await parent.getByRole("button", { name: "Me connecter" }).click();
  await parent.getByText("Numéro ou mot de passe incorrect.").waitFor();
});
await step("Parent : connexion (ancien numéro à 8 chiffres)", async () => {
  await parent.getByLabel("Mot de passe").fill(PASSWORD);
  await parent.getByRole("button", { name: "Me connecter" }).click();
  await parent.waitForURL("**/parent");
  await parent.locator(".child-card").nth(1).waitFor();
  await check(parent, "02-parent-accueil");
});
await step("Parent : fiche de l'enfant", async () => {
  // Sèna : l'école (Saint-Michel) a publié les bulletins du trimestre 1.
  await parent.locator(".child-card", { hasText: "Sèna" }).click();
  await parent.getByText("Bulletin publié par l'école").waitFor();
  await parent.locator("details.subject summary").first().click();
  await check(parent, "03-parent-fiche");
});
await step("Parent : bulletin PDF", async () => {
  const pdf = await download(parent, () => parent.getByRole("button", { name: /Télécharger le bulletin/ }).click());
  if (pdf.head !== "%PDF") throw new Error("pas un PDF");
  ok("  bulletin", `${pdf.name} en ${pdf.seconds} s`);
});
await step("Parent : trimestre sans notes", async () => {
  await parent.getByRole("tab", { name: "Trimestre 2" }).click();
  await parent.getByText("Pas encore de notes publiées").waitFor();
});
await step("Parent : pas de bulletin tant que l'école ne l'a pas publié", async () => {
  await parent.goto(`${BASE}/parent`);
  await parent.locator(".child-card", { hasText: "Koffi" }).click();
  await parent.getByText(/n'est pas encore publié/).waitFor();
  if (await parent.getByRole("button", { name: /Télécharger le bulletin/ }).count()) throw new Error("bulletin téléchargeable avant publication");
  await check(parent, "03b-parent-bulletin-non-publie");
});
await step("Parent : mon compte", async () => {
  await parent.getByRole("link", { name: "Mon compte" }).click();
  await parent.getByRole("heading", { name: "Changer de mot de passe" }).waitFor();
  await check(parent, "04-parent-compte");
});

// ---------------------------------------------------------------- Parent : première connexion
const newCtx = await context(phone);
const newcomer = await page(newCtx, "nouveau parent");
await step("Première connexion : mauvais code refusé", async () => {
  await newcomer.goto(`${BASE}/connexion`);
  await newcomer.getByRole("link", { name: /Première connexion/ }).click();
  await newcomer.getByRole("heading", { name: "Première connexion" }).waitFor();
  await newcomer.getByLabel("Numéro de téléphone").fill("01 97 00 00 02");
  await newcomer.getByLabel("Code d'accès").fill("AAAA-BBBB");
  await newcomer.getByLabel("Choisissez un mot de passe").fill("mangue-ananas-26");
  await newcomer.getByLabel("Retapez le mot de passe").fill("mangue-ananas-26");
  await newcomer.locator(".consent input").check();
  await check(newcomer, "05-premiere-connexion");
  await newcomer.getByRole("button", { name: "Enregistrer et me connecter" }).click();
  await newcomer.getByText(/Code incorrect/).waitFor();
});
await step("Première connexion : code d'accès, mot de passe choisi, connecté", async () => {
  await newcomer.getByLabel("Code d'accès").fill("pare-nt26");
  await newcomer.getByRole("button", { name: "Enregistrer et me connecter" }).click();
  await newcomer.waitForURL("**/parent");
  await newcomer.locator(".child-card").first().waitFor();
});

// ---------------------------------------------------------------- Enseignante (téléphone)
const teacherCtx = await context(phone);
const teacher = await page(teacherCtx, "enseignante");
await step("Enseignante : connexion et saisie en cours", async () => {
  await staffLogin(teacher, "0197000013");
  await teacher.locator("a.card-link", { hasText: "Interrogation 2" }).filter({ hasText: "Brouillon" }).first().click();
  await teacher.locator("input.grade-cell").first().waitFor();
  await check(teacher, "06-grille");
});
await step("Enseignante : hors barème signalé, saisie hors ligne puis resynchronisation", async () => {
  const cells = teacher.locator("input.grade-cell");
  const n = await cells.count();
  const empty = [];
  for (let i = 0; i < n; i++) if ((await cells.nth(i).inputValue()) === "") empty.push(i);
  await cells.nth(empty[0]).fill("25");
  await cells.nth(empty[0]).press("Enter");
  await teacher.getByText(/Supérieure au barème/).waitFor();
  await cells.nth(empty[0]).fill("14,5");
  await cells.nth(empty[0]).press("Enter");
  await teacherCtx.setOffline(true);
  for (const [k, i] of empty.slice(1).entries()) {
    // Le clavier numérique du téléphone n'a pas de lettres : l'absence passe par le bouton.
    if (k === 0) await teacher.locator(".abs-btn").nth(i).click();
    else {
      await cells.nth(i).fill(`${8 + k},5`);
      await cells.nth(i).press("Enter");
    }
  }
  await teacher.locator("body").click({ position: { x: 5, y: 5 } });
  await teacher.getByText(/Hors ligne/).waitFor();
  await check(teacher, "07-grille-hors-ligne");
  await teacherCtx.setOffline(false);
  await teacher.evaluate(() => window.dispatchEvent(new Event("online")));
  await teacher.getByText("Tout est enregistré").waitFor({ timeout: 20_000 });
  const footer = await teacher.locator(".grid-footer").innerText();
  if (!/(\d+)\/\1 saisies/.test(footer)) throw new Error(`après synchro : ${footer.replace(/\n/g, " | ")}`);
});
await step("Enseignante : envoi à la direction", async () => {
  await teacher.getByRole("button", { name: "Envoyer à la direction" }).click();
  await teacher.getByText("Notes envoyées à la direction.").waitFor();
});

// ---------------------------------------------------------------- Direction (ordinateur)
const dirCtx = await context(desktop);
const dir = await page(dirCtx, "direction");
await step("Direction : tableau de bord", async () => {
  await staffLogin(dir, "01 97 00 00 10");
  await dir.getByText("Parents activés").waitFor();
  await check(dir, "08-direction-accueil");
});
await step("Direction : correction avec motif, historique, publication", async () => {
  await dir.getByRole("link", { name: /Validation/ }).first().click();
  const item = dir.locator("article", { hasText: "Français" }).first();
  await item.getByRole("link", { name: "Voir les notes" }).click();
  await dir.getByRole("button", { name: /Corriger la note/ }).first().click();
  await dir.getByLabel(/Nouvelle note/).fill("16");
  await dir.getByLabel("Motif de la correction").fill("Erreur de report");
  await dir.getByRole("button", { name: "Enregistrer la correction" }).click();
  await dir.getByText("Note corrigée").waitFor();
  await dir.getByRole("button", { name: /Corriger la note/ }).first().click();
  await dir.getByText("Erreur de report").waitFor();
  await dir.getByRole("button", { name: "Fermer" }).click();
  await dir.getByRole("button", { name: "Publier aux parents" }).click();
  await dir.getByText(/les parents sont prévenus/).waitFor();
});
await step("Direction : bulletins de la classe préparés en tâche de fond", async () => {
  await dir.getByRole("link", { name: /Résultats/ }).first().click();
  await dir.getByText("Moyenne de la classe").first().waitFor();
  await check(dir, "09-direction-resultats");
  const pdf = await download(dir, () => dir.getByRole("button", { name: /Bulletins de la classe/ }).click());
  if (pdf.head !== "%PDF") throw new Error("pas un PDF");
  ok("  bulletins de classe", `${pdf.name} en ${pdf.seconds} s`);
});
await step("Direction : bulletins bloqués tant que tout n'est pas publié, puis publiés (5e A)", async () => {
  await dir.getByText("À régler avant de publier les bulletins").waitFor();
  await dir.getByLabel("Classe").selectOption({ label: "5e A · 12 élèves" });
  const publish = dir.getByRole("button", { name: /Publier les bulletins du Trimestre 1/ });
  await publish.waitFor();
  if (await publish.isDisabled()) throw new Error("5e A : publication impossible");
  await publish.click();
  await dir.getByRole("button", { name: "Publier", exact: true }).click();
  await dir.getByText(/Bulletins publiés : les parents sont prévenus/).waitFor();
  await check(dir, "09b-direction-bulletins-publies");
});
let teacherCode = null;
await step("Direction : ajout d'un enseignant, code d'accès affiché", async () => {
  await dir.getByRole("link", { name: /Personnel/ }).first().click();
  await dir.getByRole("button", { name: "Ajouter une personne" }).click();
  await dir.getByLabel("Nom complet").fill("M. ADANDE Rémi");
  await dir.getByLabel("Téléphone").fill("01 96 12 34 56");
  await dir.getByRole("button", { name: "Ajouter", exact: true }).click();
  teacherCode = (await dir.getByLabel("Code d'accès").innerText()).trim();
  await check(dir, "10-direction-code-acces");
  await dir.getByRole("button", { name: "J'ai noté le code" }).click();
});
await step("Nouvel enseignant : active son compte puis se connecte", async () => {
  const ctx = await context(phone);
  const p = await page(ctx, "nouvel enseignant");
  // Le chemin réel : depuis la page de connexion du personnel.
  await p.goto(`${BASE}/ecole/connexion`);
  await p.getByRole("link", { name: "J'ai un code d'accès" }).click();
  await p.getByRole("heading", { name: "Première connexion" }).waitFor();
  await p.getByLabel("Numéro de téléphone").fill("01 96 12 34 56");
  await p.getByLabel("Code d'accès").fill(teacherCode);
  await p.getByLabel("Choisissez un mot de passe").fill("tableau-noir-26");
  await p.getByLabel("Retapez le mot de passe").fill("tableau-noir-26");
  // Pas de case « notes de mon enfant » pour le personnel.
  if (await p.locator(".consent input").count()) throw new Error("case de consentement parent affichée");
  await check(p, "10b-premiere-connexion-personnel");
  await p.getByRole("button", { name: "Enregistrer et me connecter" }).click();
  await p.getByRole("link", { name: "Aller à l'espace du personnel" }).click();
  await p.getByLabel("Code de l'école").fill(SCHOOL);
  await p.getByLabel("Numéro de téléphone").fill("0196123456");
  await p.getByLabel("Mot de passe").fill("tableau-noir-26");
  await p.getByRole("button", { name: "Se connecter" }).click();
  await p.getByRole("heading", { name: "Mes classes" }).waitFor();
});
await step("Direction : configuration (classe, enseignant, coefficient, formule)", async () => {
  await dir.getByRole("link", { name: /Configuration/ }).first().click();
  await dir.getByRole("heading", { name: "Trimestre 1" }).waitFor();
  await dir.getByRole("tab", { name: "Classes" }).click();
  await dir.getByLabel("Nouvelle classe en 6e").fill("6e C");
  await dir.getByLabel("Nouvelle classe en 6e").press("Enter");
  await dir.getByText(/6e C · 0 élève · 6 matières/).waitFor();
  await dir.getByRole("tab", { name: "Enseignants" }).click();
  await dir.getByLabel("Enseignant de Mathématiques en 6e C").selectOption({ label: "M. ADANDE Rémi" });
  await dir.waitForResponse((r) => r.url().includes("/config/class-subjects/") && r.ok());
  await dir.getByRole("tab", { name: "Matières" }).click();
  const coef = dir.getByLabel("Coefficient de EPS en 5e");
  await coef.fill("2");
  await coef.blur();
  await dir.waitForResponse((r) => r.url().includes("/config/levels/") && r.ok());
  await dir.getByRole("tab", { name: "Calcul" }).click();
  await dir.getByText("Moyenne pondérée de toutes les évaluations").click();
  await dir.waitForResponse((r) => r.url().includes("/config/settings/") && r.ok());
  await check(dir, "11-direction-configuration");
  await dir.getByText("Moyenne des interrogations + devoirs et compositions").click();
  await dir.waitForResponse((r) => r.url().includes("/config/settings/") && r.ok());
});
await step("Nouvel enseignant : retrouve la classe qui lui a été attribuée", async () => {
  const p = await page(await context(phone), "nouvel enseignant (2)");
  await p.goto(`${BASE}/ecole/connexion`);
  await p.getByLabel("Code de l'école").fill(SCHOOL);
  await p.getByLabel("Numéro de téléphone").fill("0196123456");
  await p.getByLabel("Mot de passe").fill("tableau-noir-26");
  await p.getByRole("button", { name: "Se connecter" }).click();
  await p.getByRole("heading", { name: "6e C · Mathématiques" }).waitFor();
});
await step("Direction sur téléphone : résultats et personnel", async () => {
  const p = await page(await context({ ...phone, storageState: await dirCtx.storageState() }), "direction mobile");
  for (const [path, text, shot] of [["/ecole/resultats", "Moyenne de la classe", "12-direction-resultats-mobile"], ["/ecole/personnel", "Ajouter une personne", "12-direction-personnel-mobile"], ["/ecole/configuration?onglet=enseignants", "Mathématiques", "12-direction-configuration-mobile"]]) {
    await p.goto(`${BASE}${path}`);
    await p.getByText(text).first().waitFor();
    await check(p, shot);
  }
});

// ---------------------------------------------------------------- Secrétariat (téléphone)
const sec = await page(await context(phone), "secrétariat");
await step("Secrétariat : lettres d'accès d'une classe", async () => {
  await staffLogin(sec, "0197000011");
  await sec.goto(`${BASE}/ecole/eleves`);
  await sec.locator("article").first().waitFor();
  await sec.getByLabel("Classe").selectOption({ label: "6e A" });
  await sec.getByRole("button", { name: /Lettres d'accès de la classe/ }).waitFor();
  await check(sec, "13-secretariat-eleves");
  const pdf = await download(sec, () => sec.getByRole("button", { name: /Lettres d'accès de la classe/ }).click());
  if (pdf.head !== "%PDF") throw new Error("pas un PDF");
  ok("  lettres de la classe", `${pdf.name} en ${pdf.seconds} s`);
});
await step("Secrétariat : code d'accès d'un parent (mot de passe oublié)", async () => {
  await sec.getByRole("button", { name: /Code d'accès|Mot de passe oublié/ }).first().click();
  await sec.getByLabel("Code d'accès").waitFor();
  await check(sec, "14-secretariat-code-parent");
  await sec.getByRole("button", { name: "J'ai noté le code" }).click();
});
await step("Secrétariat : import Excel, rapport, lettres des nouveaux parents", async () => {
  await sec.goto(`${BASE}/ecole/import`);
  await sec.locator('input[type="file"]').setInputFiles(new URL("./eleves.xlsx", import.meta.url).pathname);
  await sec.getByText("Vérifiez le rapport").waitFor();
  await check(sec, "15-secretariat-rapport");
  await sec.getByRole("button", { name: /Importer les 2 élèves/ }).click();
  await sec.getByText(/2 élèves importés, 1 nouveau parent/).waitFor();
  const pdf = await download(sec, () => sec.getByRole("button", { name: "Imprimer la lettre d'accès" }).click());
  if (pdf.head !== "%PDF") throw new Error("pas un PDF");
  await check(sec, "16-secretariat-import-fait");
});
await step("Secrétariat : inscription manuelle", async () => {
  await sec.goto(`${BASE}/ecole/eleves`);
  await sec.getByRole("button", { name: "Inscrire un élève" }).click();
  await sec.getByLabel("Matricule").fill(`MAN-${Date.now() % 100000}`);
  await sec.getByLabel("Nom", { exact: true }).fill("Bossou");
  await sec.getByLabel("Prénom(s)").fill("Clarisse");
  await sec.getByLabel("Date de naissance").fill("2014-04-02");
  await sec.getByLabel("Nom du parent").fill("BOSSOU Alice");
  await sec.getByLabel("Téléphone du parent").fill("0196778899");
  await sec.getByRole("button", { name: "Inscrire", exact: true }).click();
  await sec.getByText(/Élève inscrit/).waitFor();
});

// ---------------------------------------------------------------- Retour chez le parent
await step("Parent : la note publiée arrive dans les nouveautés", async () => {
  await parent.goto(`${BASE}/parent/notifications`);
  await parent.getByText(/Note corrigée|Nouvelle note pour .* en Français/).first().waitFor();
  await check(parent, "17-parent-nouveautes");
});
await step("Rôles : un parent n'entre pas dans l'espace école", async () => {
  await parent.goto(`${BASE}/ecole`);
  await parent.waitForURL("**/ecole/connexion");
});

await browser.close();
console.log(results.join("\n"));
console.log(`\nErreurs JavaScript : ${errors.length ? `\n${errors.join("\n")}` : "aucune"}`);
const failures = results.filter((r) => r.startsWith("✗")).length;
console.log(`\n${results.filter((r) => r.startsWith("✓ ") && !r.startsWith("✓  ")).length} étapes réussies, ${failures} en échec.`);
process.exit(failures || errors.length ? 1 : 0);
