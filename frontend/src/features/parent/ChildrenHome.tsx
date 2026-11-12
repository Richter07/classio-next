import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../shared/api/client";
import { fmt, initials, relative, today } from "../../shared/format";
import { Icon } from "../../shared/ui/Icon";
import { Empty, ErrorBox, Spinner } from "../../shared/ui/kit";

type Child = {
  id: string;
  school_id: string;
  first_name: string;
  last_name: string;
  classroom: string | null;
  school: { name: string; color: string };
  period: string | null;
  average: number | null;
  last_grade: { subject: string; value: number | null; max_score: number; is_absent: boolean; published_at: string; kind: string } | null;
};

export function ChildrenHome() {
  const query = useQuery({ queryKey: ["parent", "children"], queryFn: () => api<{ children: Child[] }>("parent/children/") });

  return (
    <main className="content">
      <div className="page-head">
        <span className="muted small" style={{ textTransform: "capitalize" }}>
          {today()}
        </span>
        <h1>Bonjour</h1>
      </div>
      {query.isLoading && <Spinner />}
      {query.error && <ErrorBox error={query.error} retry={() => void query.refetch()} />}
      {query.data?.children.length === 0 && (
        <Empty icon="users" title="Aucun enfant rattaché">
          Votre numéro n'est encore rattaché à aucun élève. Rapprochez-vous du secrétariat de l'école.
        </Empty>
      )}
      <div className="children-grid stack">
        {query.data?.children.map((child) => (
          <Link key={child.id} to={`/parent/enfant/${child.school_id}/${child.id}`} className="card card-link child-card">
            <div className="child-head">
              <span className="avatar" style={{ background: child.school.color }} aria-hidden>
                {initials(child.first_name, child.last_name)}
              </span>
              <div className="grow">
                <h2 className="ellipsis">
                  {child.first_name} {child.last_name}
                </h2>
                <p className="muted small ellipsis">
                  {child.classroom ?? "Sans classe"} · {child.school.name}
                </p>
              </div>
              <Icon name="next" />
            </div>
            <div className="child-figures">
              {child.average !== null ? (
                <div>
                  <span className="muted small">Moyenne du bulletin{child.period && ` · ${child.period}`}</span>
                  <div className="big-average">
                    {fmt(child.average)}
                    <small> /20</small>
                  </div>
                </div>
              ) : (
                <p className="muted small">Moyenne et rang : au premier bulletin publié par l'école.</p>
              )}
              {child.last_grade && (
                <div className="last-grade">
                  <span className="muted">Dernière note :</span>
                  <strong>
                    {child.last_grade.subject}{" "}
                    {child.last_grade.is_absent ? "absent" : `${fmt(child.last_grade.value)}/${fmt(child.last_grade.max_score)}`}
                  </strong>
                  <span className="muted small">{relative(child.last_grade.published_at)}</span>
                </div>
              )}
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
