import { useEffect, useState } from "react";

/** Installation de Classio sur l'écran d'accueil, à la place d'une application du Play Store.
 *
 *  Chrome sur Android annonce une seule fois, au chargement de la page, que l'installation est
 *  possible (événement « beforeinstallprompt »). Ce module est importé dès main.tsx pour ne pas
 *  manquer cet événement, qui arrive souvent avant l'affichage du premier écran. */

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let deferred: InstallPromptEvent | null = null;
let installed = false;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    // On garde l'événement pour proposer l'installation au bon moment, avec nos mots.
    event.preventDefault();
    deferred = event as InstallPromptEvent;
    notify();
  });
  window.addEventListener("appinstalled", () => {
    installed = true;
    deferred = null;
    notify();
  });
}

/** Comment installer sur cet appareil :
 *  - installed : déjà ouverte comme une application ;
 *  - prompt : Chrome (Android ou ordinateur) propose l'installation, un bouton suffit ;
 *  - ios : iPhone ou iPad, l'installation se fait par le menu Partager ;
 *  - in-app : navigateur intégré à WhatsApp, Facebook… qui ne sait pas installer ;
 *  - android : Android sans proposition de Chrome, l'installation se fait par le menu ⋮ ;
 *  - none : ordinateur sans installation possible, on ne propose rien. */
export type InstallMode = "installed" | "prompt" | "ios" | "in-app" | "android" | "none";

function standalone() {
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export function installMode(): InstallMode {
  if (installed || standalone()) return "installed";
  if (deferred) return "prompt";
  const ua = navigator.userAgent;
  if (/FBAN|FBAV|FB_IAB|Instagram|WhatsApp|Line\/|Snapchat|TikTok|; wv\)/i.test(ua)) return "in-app";
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  if (ios) return "ios";
  if (/Android/i.test(ua)) return "android";
  return "none";
}

export function useInstall() {
  const [mode, setMode] = useState<InstallMode>(installMode);
  useEffect(() => {
    const update = () => setMode(installMode());
    listeners.add(update);
    return () => {
      listeners.delete(update);
    };
  }, []);

  async function install() {
    if (!deferred) return;
    const event = deferred;
    deferred = null; // Chrome n'accepte qu'un seul appel à prompt() par événement.
    await event.prompt();
    const { outcome } = await event.userChoice;
    if (outcome === "accepted") installed = true;
    notify();
  }

  return { mode, install };
}
