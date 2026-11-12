import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../../shared/api/client";
import { startBackgroundSync } from "../../shared/offline/sync";
import { isDirection, isOffice, isTeacher, useLogout, useMe, type Me } from "../../shared/session";
import { Icon, type IconName } from "../../shared/ui/Icon";
import { RouteProgress, Spinner } from "../../shared/ui/kit";

type NavItem = { to: string; label: string; icon: IconName; badge?: number; end?: boolean; desktopOnly?: boolean };

export type Overview = {
  year: string | null; students: number; classrooms: number; to_validate: number; to_publish: number;
  published_grades: number; guardians: number; guardians_active: number;
  setup: { periods: number; classrooms: number; unassigned: number };
};

export const useOverview = (enabled: boolean) =>
  useQuery({ queryKey: ["direction", "overview"], queryFn: () => api<Overview>("direction/overview/"), enabled });

function navFor(me: Me, pending: number): NavItem[] {
  const items: NavItem[] = [{ to: "/ecole", label: "Accueil", icon: "home", end: true }];
  if (isTeacher(me)) items.push({ to: "/ecole/saisie", label: "Saisie", icon: "edit" });
  if (isDirection(me)) {
    items.push({ to: "/ecole/validation", label: "Validation", icon: "check", badge: pending });
    items.push({ to: "/ecole/resultats", label: "Résultats", icon: "chart" });
  }
  const staffLink: NavItem[] = isDirection(me)
    ? [
        { to: "/ecole/personnel", label: "Personnel", icon: "user" },
        // Sur téléphone, la configuration s'ouvre depuis l'accueil : cinq onglets au plus.
        { to: "/ecole/configuration", label: "Configuration", icon: "edit", desktopOnly: true },
      ]
    : [];
  if (isOffice(me)) {
    items.push({ to: "/ecole/eleves", label: "Élèves", icon: "users" });
    // La direction importe depuis la page Élèves : cinq onglets au plus sur téléphone.
    if (!isDirection(me)) items.push({ to: "/ecole/import", label: "Import", icon: "upload" });
  }
  return [...items, ...staffLink];
}

export function StaffLayout() {
  const { data: me, isLoading } = useMe();
  const direction = !!me && isDirection(me);
  const overview = useOverview(direction);
  const logout = useLogout();
  const navigate = useNavigate();
  // La file hors ligne ne concerne que le personnel : elle n'est chargée que dans cet espace.
  useEffect(() => startBackgroundSync(), []);

  if (isLoading) return <Spinner />;
  if (!me?.roles.length || !me.school) return <Navigate to="/ecole/connexion" replace />;

  const nav = navFor(me, (overview.data?.to_validate ?? 0) + (overview.data?.to_publish ?? 0));
  // Un enseignant seul n'a qu'un écran utile : pas de barre de navigation qui ne mène nulle part.
  const single = nav.length <= 2 && isTeacher(me) && !isDirection(me) && !isOffice(me);
  const links = (className?: string, mobile = false) =>
    nav.filter((item) => !(mobile && item.desktopOnly)).map((item) => (
      <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `${className ?? ""} ${isActive ? "active" : ""}`}>
        <Icon name={item.icon} size={22} />
        <span>{item.label}</span>
        {!!item.badge && <span className="dot">{item.badge}</span>}
      </NavLink>
    ));

  return (
    <div className={`staff-shell ${single ? "single" : ""}`}>
      <header className="topbar" style={{ background: me.school.color_primary }}>
        <div className="title">
          <strong>{me.school.name}</strong>
          <span>{me.full_name}</span>
        </div>
        <button
          className="icon-btn"
          aria-label="Se déconnecter"
          onClick={async () => {
            await logout();
            navigate("/ecole/connexion", { replace: true });
          }}
        >
          <Icon name="logout" />
        </button>
      </header>
      {!single && (
        <nav className="sidebar" aria-label="Navigation principale">
          {links()}
        </nav>
      )}
      <div>
        <RouteProgress />
      <Outlet />
      </div>
      {!single && (
        <nav className="tabbar" aria-label="Navigation principale">
          {links(undefined, true)}
        </nav>
      )}
    </div>
  );
}
