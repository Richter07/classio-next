import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fileUrl } from "../../shared/api/client";
import { fmt, fmtDate, fmtFullDate, shortPeriod } from "../../shared/format";
import { Icon } from "../../shared/ui/Icon";
import { Badge, DownloadButton, Empty, ErrorBox, Segmented, Select, Spinner } from "../../shared/ui/kit";

type GradeItem = { id: string; kind: string; title: string; date: string | null; value: number | null; max_score: number; is_absent: boolean };
type Subject = { id: string; name: string; teacher: string; coefficient: number; average: number | null; class_average: number | null; rank_label: string | null; grades: GradeItem[] };
type Detail = {
  student: { first_name: string; last_name: string; matricule: string };
  school: { id: string; name: string };
  classroom: string;
  year: { id: string; label: string };
  years: { id: string; label: string; classroom: string }[];
  periods: { id: string; name: string }[];
  period: { id: string; name: string } | null;
  summary: {
    average: number | null; rank: number | null; rank_label: string; class_size: number;
    class_average: number | null; highest: number | null; lowest: number | null; appreciation: string; max_score: number;
    released_at: string;
  } | null;
  subjects: Subject[];
  released?: boolean;
  has_bulletin?: boolean;
};

function Trend({ mine, reference }: { mine: number | null; reference: number | null }) {
  if (mine === null || reference === null) return null;
  const diff = Math.round((mine - reference) * 100) / 100;
  if (Math.abs(diff) < 0.25)
    return <span className="trend trend-same">≈ moyenne de la classe</span>;
  const up = diff > 0;
  return (
    <span className={`trend ${up ? "trend-up" : "trend-down"}`}>
      <Icon name={up ? "up" : "down"} size={14} />
      {up ? "+" : "−"}
      {fmt(Math.abs(diff))} {up ? "au-dessus" : "en dessous"} de la moyenne de classe
    </span>
  );
}

function Scale({ summary }: { summary: NonNullable<Detail["summary"]> }) {
  const pct = (v: number | null) => (v === null ? 0 : Math.max(0, Math.min(100, (v / summary.max_score) * 100)));
  return (
    <div aria-hidden className="scale">
      {summary.lowest !== null && summary.highest !== null && (
        <span className="range" style={{ left: `${pct(summary.lowest)}%`, width: `${pct(summary.highest) - pct(summary.lowest)}%` }} />
      )}
      {summary.class_average !== null && (
        <>
          <span className="tick" style={{ left: `${pct(summary.class_average)}%` }} />
          <span className="tick-label" style={{ left: `${pct(summary.class_average)}%` }}>
            classe {fmt(summary.class_average)}
          </span>
        </>
      )}
      {summary.average !== null && <span className="marker" style={{ left: `${pct(summary.average)}%` }} />}
    </div>
  );
}

export function ChildDetail() {
  const { schoolId, studentId } = useParams();
  const [period, setPeriod] = useState<string | null>(null);
  const [year, setYear] = useState<string | null>(null);
  const params = new URLSearchParams();
  if (period) params.set("period", period);
  if (year) params.set("year", year);
  const query = useQuery({
    queryKey: ["parent", "child", schoolId, studentId, period, year],
    queryFn: () => api<Detail>(`parent/children/${schoolId}/${studentId}/?${params}`),
    placeholderData: (previous) => previous,
  });
  const data = query.data;

  return (
    <main className="content">
      <Link to="/parent" className="back">
        <Icon name="back" /> Mes enfants
      </Link>
      {query.isLoading && <Spinner />}
      {query.error && <ErrorBox error={query.error} retry={() => void query.refetch()} />}
      {data && (
        <>
          <div className="page-head">
            <h1>
              {data.student.first_name} {data.student.last_name}
            </h1>
            <p className="muted">
              {data.classroom} · {data.school.name} · {data.year.label}
            </p>
          </div>

          {data.years.length > 1 && (
            <Select aria-label="Année scolaire" value={data.year.id} onChange={(e) => { setYear(e.target.value); setPeriod(null); }}>
              {data.years.map((y) => (
                <option key={y.id} value={y.id}>
                  {y.label} · {y.classroom}
                </option>
              ))}
            </Select>
          )}

          {data.periods.length > 0 && (
            <Segmented
              label="Période"
              value={data.period?.id ?? ""}
              options={data.periods.map((p) => ({ value: p.id, label: shortPeriod(p.name), fullLabel: p.name }))}
              onChange={setPeriod}
            />
          )}

          {data.summary ? (
            <section className="summary" aria-label="Résultats de la période">
              <div className="row-between">
                <div>
                  <span className="muted small">
                    Moyenne générale · <span className="nowrap">{data.period?.name}</span>
                  </span>
                  <div className="big-average">
                    {fmt(data.summary.average)}
                    <small> /{fmt(data.summary.max_score)}</small>
                  </div>
                </div>
                {data.summary.appreciation && <Badge tone="warning">{data.summary.appreciation}</Badge>}
              </div>
              <Scale summary={data.summary} />
              <div className="summary-grid">
                <div>
                  <strong>{data.summary.rank_label}</strong>
                  <span>sur {data.summary.class_size}</span>
                </div>
                <div>
                  <strong>{fmt(data.summary.class_average)}</strong>
                  <span>moy. classe</span>
                </div>
                <div>
                  <strong>
                    {fmt(data.summary.lowest)} – {fmt(data.summary.highest)}
                  </strong>
                  <span>écart classe</span>
                </div>
              </div>
              <p className="muted small">Bulletin publié par l'école le {fmtFullDate(data.summary.released_at)}.</p>
              {data.has_bulletin && data.period && (
                <DownloadButton
                  url={fileUrl(`parent/children/${schoolId}/${studentId}/bulletin.pdf?period=${data.period.id}&year=${data.year.id}`)}
                  filename={`bulletin-${data.student.first_name}-${data.period.name}.pdf`.replace(/\s+/g, "-")}
                  busyLabel="Préparation du bulletin…"
                >
                  Télécharger le bulletin (PDF)
                </DownloadButton>
              )}
            </section>
          ) : data.subjects.some((s) => s.grades.length > 0) ? (
            <div className="notice notice-info">
              <Icon name="clock" />
              <p>
                Le bulletin du {data.period?.name} n'est pas encore publié. La moyenne générale, le rang et le bulletin apparaîtront
                quand l'école le publiera : vous serez prévenu. En attendant, voici les notes déjà publiées.
              </p>
            </div>
          ) : (
            <Empty icon="clock" title="Pas encore de notes publiées">
              Les notes de cette période apparaîtront ici dès que l'école les aura publiées. Vous serez prévenu.
            </Empty>
          )}

          {data.subjects.some((s) => s.grades.length > 0) && (
            <section className="stack-sm" aria-label="Notes par matière">
              <h2>Par matière</h2>
              {data.subjects.map((subject) => (
                <details key={subject.id} className="card subject">
                  <summary>
                    <div className="grow">
                      <strong className="ellipsis" style={{ display: "block" }}>
                        {subject.name}
                      </strong>
                      <span className="muted small">
                        Coef. {fmt(subject.coefficient)} · {subject.grades.length} note{subject.grades.length > 1 ? "s" : ""}
                        {subject.rank_label && subject.average !== null && ` · ${subject.rank_label}`}
                      </span>
                      <div>
                        <Trend mine={subject.average} reference={subject.class_average} />
                      </div>
                    </div>
                    {subject.average !== null && (
                      <div className="subject-average">
                        <strong>{fmt(subject.average)}</strong>
                        <span className="muted small">classe {fmt(subject.class_average)}</span>
                      </div>
                    )}
                    <span className="chev">
                      <Icon name="next" />
                    </span>
                  </summary>
                  {subject.grades.length === 0 ? (
                    <p className="muted small" style={{ padding: "12px 16px" }}>
                      Aucune note publiée.
                    </p>
                  ) : (
                    <ul className="grade-list">
                      {subject.grades.map((grade) => (
                        <li key={grade.id}>
                          <div>
                            <strong>{grade.title || grade.kind}</strong>
                            <div className="muted small">
                              {grade.kind}
                              {grade.date && ` · ${fmtDate(grade.date)}`}
                            </div>
                          </div>
                          <span className="grade-value">
                            {grade.is_absent ? <Badge>Absent · 0</Badge> : `${fmt(grade.value)} / ${fmt(grade.max_score)}`}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {subject.teacher && (
                    <p className="muted small" style={{ padding: "0 16px 12px" }}>
                      Enseignant : {subject.teacher}
                    </p>
                  )}
                </details>
              ))}
            </section>
          )}
        </>
      )}
    </main>
  );
}
