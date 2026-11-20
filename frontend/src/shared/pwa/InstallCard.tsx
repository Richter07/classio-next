import { useState } from "react";
import { Icon } from "../ui/Icon";
import { Button } from "../ui/kit";
import { useInstall } from "./install";

/** Libellé entre guillemets français, avec espaces insécables. */
const q = (label: string) => `«\u00a0${label}\u00a0»`;

const DISMISS_KEY = "classio.install.dismissed";
const DISMISS_DAYS = 14;

function dismissedRecently() {
  try {
    const until = Number(localStorage.getItem(DISMISS_KEY));
    return Number.isFinite(until) && until > Date.now();
  } catch {
    return false;
  }
}

function rememberDismiss() {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now() + DISMISS_DAYS * 86_400_000));
  } catch {
    // Navigation privée ou stockage bloqué : la carte reviendra au prochain chargement.
  }
}

/** Invitation à installer Classio sur l'écran d'accueil. Il n'y a pas d'application sur le
 *  Play Store : c'est d'ici que le parent ou l'enseignant « télécharge » Classio.
 *  `permanent` : affichée sans bouton de fermeture (page Mon compte). */
export function InstallCard({ permanent = false }: { permanent?: boolean }) {
  const { mode, install } = useInstall();
  const [hidden, setHidden] = useState(() => !permanent && dismissedRecently());

  if (hidden || mode === "installed" || mode === "none") return null;

  return (
    <section className="card install-card" aria-labelledby="install-title">
      <div className="row-between">
        <h2 id="install-title" className="row">
          <Icon name="phone" /> Installer Classio sur ce téléphone
        </h2>
        {!permanent && (
          <button
            className="icon-btn"
            aria-label="Plus tard"
            onClick={() => {
              rememberDismiss();
              setHidden(true);
            }}
          >
            <Icon name="x" size={20} />
          </button>
        )}
      </div>
      <p className="muted small">
        Une icône sur l'écran d'accueil, comme une application. Rien à chercher sur le Play Store, et presque rien à
        télécharger.
      </p>
      {mode === "prompt" && (
        <Button icon="download" onClick={() => void install()}>
          Installer
        </Button>
      )}
      {mode === "ios" && (
        <ol className="install-steps">
          <li>
            Touchez le bouton <strong>Partager</strong>{"\u00a0"}
            <Icon name="share" size={18} label="Partager" /> en bas de l'écran.
          </li>
          <li>
            Choisissez <strong>{q("Sur l'écran d'accueil")}</strong>, puis <strong>Ajouter</strong>.
          </li>
        </ol>
      )}
      {mode === "android" && (
        <ol className="install-steps">
          <li>
            Dans Chrome, touchez le menu <strong>⋮</strong> en haut à droite.
          </li>
          <li>
            Choisissez <strong>{q("Installer l'application")}</strong> ou <strong>{q("Ajouter à l'écran d'accueil")}</strong>.
          </li>
        </ol>
      )}
      {mode === "in-app" && (
        <p className="small">
          Vous avez ouvert Classio depuis une autre application (WhatsApp, Facebook…). Touchez le menu{" "}
          <strong>⋮</strong> puis <strong>{q("Ouvrir dans le navigateur")}</strong> (Chrome ou Safari) : vous pourrez
          alors l'installer.
        </p>
      )}
    </section>
  );
}
