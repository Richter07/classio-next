import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom";
import { Icon } from "../shared/ui/Icon";

/** Une page d'erreur compréhensible, au lieu de l'écran technique (en anglais) par défaut. */
export function RouteError() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  // Une nouvelle version de l'application a été déployée : l'ancien fichier n'existe plus.
  const stale = error instanceof Error && /dynamically imported module|Failed to fetch/i.test(error.message);
  return (
    <main className="auth">
      <div className="auth-card">
        <div className="panel" style={{ textAlign: "center" }}>
          <span className="empty-icon" style={{ margin: "0 auto" }}>
            <Icon name="alert" size={28} />
          </span>
          <h1>{notFound ? "Page introuvable" : stale ? "Nouvelle version disponible" : "Un problème est survenu"}</h1>
          <p className="muted">
            {stale ? "Rechargez la page pour continuer." : "Vos données ne sont pas perdues. Réessayez dans un instant."}
          </p>
          <button className="btn btn-primary btn-block" onClick={() => window.location.reload()}>
            Recharger la page
          </button>
          <Link to="/" className="link">
            Retour à l'accueil
          </Link>
        </div>
      </div>
    </main>
  );
}
