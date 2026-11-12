import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../../shared/api/client";
import { relative } from "../../shared/format";
import { Icon } from "../../shared/ui/Icon";
import { Empty, ErrorBox, Spinner } from "../../shared/ui/kit";
import { useNotifications } from "./ParentLayout";

export function Notifications() {
  const query = useNotifications();
  const client = useQueryClient();
  const unread = query.data?.unread ?? 0;

  useEffect(() => {
    // Ouvrir la page vaut lecture ; la liste garde son surlignage jusqu'à la prochaine visite.
    if (unread > 0) {
      void api("parent/notifications/", { method: "POST" }).then(() =>
        client.setQueryData(["parent", "notifications"], (old: typeof query.data) => (old ? { ...old, unread: 0 } : old)),
      );
    }
  }, [unread, client]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="content">
      <Link to="/parent" className="back">
        <Icon name="back" /> Mes enfants
      </Link>
      <h1>Nouveautés</h1>
      {query.isLoading && <Spinner />}
      {query.error && <ErrorBox error={query.error} />}
      {query.data?.items.length === 0 && <Empty icon="bell" title="Rien de nouveau">Vous serez prévenu à chaque nouvelle note.</Empty>}
      {query.data && query.data.items.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          {query.data.items.map((n) => (
            <Link key={n.id} to={n.link || "/parent"} className={`notif ${n.read ? "" : "unread"}`}>
              <span className="pin" aria-hidden />
              <div className="grow">
                <p>{n.message}</p>
                <p className="muted small">
                  {n.school} · {relative(n.created_at)}
                  {!n.read && <span className="visually-hidden"> · non lue</span>}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
