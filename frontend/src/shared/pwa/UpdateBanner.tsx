import { useEffect, useState } from "react";
import { useRegisterSW } from "virtual:pwa-register/react";

const CHECK_EVERY = 60 * 60 * 1000;

/** Nouvelle version de Classio déployée : on le dit, et l'utilisateur choisit le moment.
 *
 *  Une application installée reste ouverte des jours entiers. Sans ce bandeau, elle continuerait
 *  d'afficher l'ancienne version ; et recharger d'office pourrait couper un enseignant en pleine
 *  saisie. Tant qu'il n'a pas mis à jour, l'ancienne version reste complète en cache : elle
 *  continue de fonctionner normalement. */
export function UpdateBanner() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      if (!registration) return;
      const check = () => {
        if (navigator.onLine) void registration.update().catch(() => undefined);
      };
      setInterval(check, CHECK_EVERY);
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") check();
      });
    },
  });
  const [busy, setBusy] = useState(false);

  if (!needRefresh) return null;
  return (
    <div className="update-banner" role="status">
      <span>Une nouvelle version de Classio est disponible.</span>
      <button
        className="btn btn-primary"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          void updateServiceWorker();
          // Page ouverte lors de la toute première visite : elle n'est pas encore pilotée par le
          // service worker, rien ne la rechargerait. Un rechargement simple suffit alors.
          setTimeout(() => window.location.reload(), 3000);
        }}
      >
        {busy ? "Mise à jour…" : "Mettre à jour"}
      </button>
    </div>
  );
}

/** Bandeau « hors connexion » de l'espace parent : les données affichées datent du dernier
 *  chargement (elles ne sont jamais conservées sur le téléphone). */
export function OfflineBanner() {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  if (online) return null;
  return (
    <div className="offline-banner" role="status">
      Pas de connexion : les informations affichées peuvent ne pas être à jour.
    </div>
  );
}
