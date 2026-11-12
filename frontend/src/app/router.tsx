import { createBrowserRouter, Link, Navigate } from "react-router-dom";
import { ParentLogin } from "../features/auth/ParentLogin";
import { RouteError } from "./RouteError";
import { useMe } from "../shared/session";
import { Spinner } from "../shared/ui/kit";

/** Racine : chacun retrouve son espace, le parent par défaut (c'est le public principal). */
function Home() {
  const { data: me, isLoading } = useMe();
  if (isLoading) return <Spinner />;
  if (me?.roles.length && me.school) return <Navigate to="/ecole" replace />;
  if (me?.is_parent) return <Navigate to="/parent" replace />;
  return <ParentLogin />;
}

/** Adresse inconnue : on le dit, plutôt que de renvoyer en silence à l'accueil. Souvent, c'est
 *  une ancienne version de l'application restée en mémoire du navigateur : recharger suffit. */
function NotFound() {
  return (
    <main className="content">
      <div className="page-head">
        <h1>Page introuvable</h1>
        <p className="muted">
          Cette adresse n'existe pas, ou votre navigateur affiche une ancienne version de Classio.
        </p>
      </div>
      <div className="row wrap">
        <button className="btn btn-primary" onClick={() => window.location.reload()}>
          Recharger l'application
        </button>
        <Link to="/" className="btn btn-ghost">
          Accueil
        </Link>
      </div>
    </main>
  );
}

// Chaque espace est chargé à la demande : un parent ne télécharge jamais l'outil de saisie.
const parent = () => import("../features/parent/routes");
const staff = () => import("../features/staff/routes");

export const router = createBrowserRouter([
  {
    errorElement: <RouteError />,
    // Sur réseau lent, une page se charge à la demande : un indicateur plutôt qu'un écran blanc.
    hydrateFallbackElement: <Spinner />,
    children: [
  { path: "/", element: <Home /> },
  { path: "/connexion", element: <ParentLogin /> },
  { path: "/activation", lazy: async () => ({ Component: (await import("../features/auth/Activation")).Activation }) },
  { path: "/confidentialite", lazy: async () => ({ Component: (await import("../features/auth/Privacy")).Privacy }) },
  {
    path: "/parent",
    lazy: async () => ({ Component: (await parent()).ParentLayout }),
    children: [
      { index: true, lazy: async () => ({ Component: (await parent()).ChildrenHome }) },
      { path: "enfant/:schoolId/:studentId", lazy: async () => ({ Component: (await parent()).ChildDetail }) },
      { path: "notifications", lazy: async () => ({ Component: (await parent()).Notifications }) },
      { path: "compte", lazy: async () => ({ Component: (await parent()).Account }) },
      { path: "*", element: <NotFound /> },
    ],
  },
  { path: "/ecole/connexion", lazy: async () => ({ Component: (await staff()).StaffLogin }) },
  {
    path: "/ecole",
    lazy: async () => ({ Component: (await staff()).StaffLayout }),
    children: [
      { index: true, lazy: async () => ({ Component: (await staff()).StaffHome }) },
      { path: "saisie", lazy: async () => ({ Component: (await staff()).MyClasses }) },
      { path: "saisie/:assessmentId", lazy: async () => ({ Component: (await staff()).GradeGrid }) },
      { path: "validation", lazy: async () => ({ Component: (await staff()).Validation }) },
      { path: "validation/:assessmentId", lazy: async () => ({ Component: (await staff()).GradeGrid }) },
      { path: "resultats", lazy: async () => ({ Component: (await staff()).ResultsPage }) },
      { path: "eleves", lazy: async () => ({ Component: (await staff()).Students }) },
      { path: "import", lazy: async () => ({ Component: (await staff()).ImportPage }) },
      { path: "personnel", lazy: async () => ({ Component: (await staff()).StaffPage }) },
      { path: "configuration", lazy: async () => ({ Component: (await staff()).Configuration }) },
      { path: "*", element: <NotFound /> },
    ],
  },
  { path: "*", element: <NotFound /> },
    ],
  },
]);
