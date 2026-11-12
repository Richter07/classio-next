import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, Outlet } from "react-router-dom";
import { api } from "../../shared/api/client";
import { useMe } from "../../shared/session";
import { Icon } from "../../shared/ui/Icon";
import { RouteProgress, Spinner } from "../../shared/ui/kit";
import logoDark from "../../shared/ui/logo-on-dark.svg";

export type Notifications = {
  unread: number;
  items: { id: string; kind: string; message: string; link: string; created_at: string; read: boolean; school: string; student: string | null }[];
};

export const useNotifications = () =>
  useQuery({ queryKey: ["parent", "notifications"], queryFn: () => api<Notifications>("parent/notifications/") });

export function ParentLayout() {
  const { data: me, isLoading } = useMe();
  const notifications = useNotifications();

  if (isLoading) return <Spinner />;
  if (!me?.is_parent) return <Navigate to="/connexion" replace />;
  const unread = notifications.data?.unread ?? 0;

  return (
    <>
      <header className="topbar">
        <Link to="/parent" className="title" aria-label="Accueil">
          <img className="topbar-logo" src={logoDark} alt="Classio" width={86} height={28} />
        </Link>
        <Link to="/parent/notifications" className="icon-btn" aria-label={`Nouveautés${unread ? `, ${unread} non lues` : ""}`}>
          <Icon name="bell" />
          {unread > 0 && <span className="dot">{unread > 9 ? "9+" : unread}</span>}
        </Link>
        <Link to="/parent/compte" className="icon-btn" aria-label="Mon compte">
          <Icon name="user" />
        </Link>
      </header>
      <RouteProgress />
      <Outlet />
    </>
  );
}
