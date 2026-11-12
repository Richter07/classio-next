import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, fileUrl } from "../../shared/api/client";
import { fmt, fmtFullDate } from "../../shared/format";
import { Icon } from "../../shared/ui/Icon";
import { Badge, Button, Dialog, DownloadButton, Empty, JobButton, ErrorBox, Field, Segmented, Select, Spinner, Stat, useToast } from "../../shared/ui/kit";

type Release = {
  released_at: string | null; released_count: number; enrolled: number; assessments: number;
  blockers: string[]; subjects_without_grades: string[]; outdated: boolean;
};

/** Les parents ne voient moyenne générale, rang et bulletin qu'après cette publication. */
function ReleasePanel({ classroom, period, periodName }: { classroom: Classroom; period: string; periodName: string }) {
  const client = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = useState<"release" | "withdraw" | null>(null);
  const url = `direction/classes/${classroom.id}/release/?period=${period}`;
  const state = useQuery({ queryKey: ["direction", "release", classroom.id, period], queryFn: () => api<Release>(url) });
  const act = useMutation({
    mutationFn: (kind: "release" | "withdraw") => api<Release>(url, { method: kind === "release" ? "POST" : "DELETE" }),
    onSuccess: (data, kind) => {
      client.setQueryData(["direction", "release", classroom.id, period], data);
      toast(kind === "release" ? "Bulletins publiés : les parents sont prévenus." : "Bulletins retirés : les parents ne les voient plus.");
      setConfirm(null);
    },
    onError: (e) => { toast(e.message, "danger"); void state.refetch(); setConfirm(null); },
  });
  const s = state.data;
  if (!s) return null;
  const ready = s.blockers.length === 0 && s.assessments > 0;
  return (
    <section className="card stack-sm" aria-label="Bulletins aux parents">
      <div className="row-between">
        <h2>Bulletins aux parents · {classroom.name}</h2>
        {s.released_at ? <Badge tone="success">Publiés</Badge> : <Badge tone="warning">Non publiés</Badge>}
      </div>
      {s.released_at ? (
        <p className="small">
          Publiés le {fmtFullDate(s.released_at)} : les {s.released_count} familles voient la moyenne, le rang et le bulletin PDF.
          Les chiffres sont figés à cette date.
        </p>
      ) : (
        <p className="muted small">
          Tant que vous ne publiez pas, les parents voient les notes une à une, mais ni moyenne générale, ni rang, ni bulletin.
        </p>
      )}
      {s.outdated && (
        <div className="notice notice-warning"><Icon name="alert" /><p>Des notes ont été corrigées depuis la publication : publiez à nouveau pour mettre les bulletins à jour.</p></div>
      )}
      {s.blockers.length > 0 && (
        <div className="notice notice-warning">
          <Icon name="alert" />
          <div>
            <p><strong>À régler avant de publier les bulletins :</strong></p>
            <ul className="small">{s.blockers.map((b) => <li key={b}>{b}</li>)}</ul>
          </div>
        </div>
      )}
      {s.subjects_without_grades.length > 0 && (
        <p className="muted small">Sans aucune note sur la période : {s.subjects_without_grades.join(", ")}. Ces matières n'entreront pas dans la moyenne.</p>
      )}
      <div className="row wrap">
        <Button icon="send" disabled={!ready} onClick={() => setConfirm("release")}>
          {s.released_at ? "Publier à nouveau" : `Publier les bulletins du ${periodName}`}
        </Button>
        {s.released_at && <Button variant="ghost" onClick={() => setConfirm("withdraw")}>Retirer</Button>}
      </div>
      <Dialog title={confirm === "withdraw" ? "Retirer les bulletins ?" : "Publier les bulletins ?"} open={!!confirm} onClose={() => setConfirm(null)}>
        <p>
          {confirm === "withdraw"
            ? "Les parents ne verront plus ni la moyenne, ni le rang, ni le bulletin de cette période."
            : `Les ${s.enrolled} familles de ${classroom.name} pourront consulter et télécharger le bulletin du ${periodName}. Elles sont prévenues dans l'application.`}
        </p>
        <Button variant={confirm === "withdraw" ? "danger" : "primary"} busy={act.isPending} onClick={() => confirm && act.mutate(confirm)}>
          {confirm === "withdraw" ? "Retirer les bulletins" : "Publier"}
        </Button>
      </Dialog>
    </section>
  );
}

type Classroom = { id: string; name: string; level: string; students: number; periods: { id: string; name: string }[] };
type Results = {
  classroom: string; period: { id: string; name: string }; max_score: number; class_average: number | null;
  highest: number | null; lowest: number | null; ranked: number; to_publish: number;
  subjects: { id: string; name: string; coefficient: number; class_average: number | null }[];
  students: { id: string; name: string; average: number | null; rank: number | null; rank_label: string; appreciation: string; subjects: Record<string, number | null> }[];
};

export function ResultsPage() {
  const classes = useQuery({ queryKey: ["direction", "classes"], queryFn: () => api<{ items: Classroom[] }>("direction/classes/") });
  const [classId, setClassId] = useState<string | null>(null);
  const [periodId, setPeriodId] = useState<string | null>(null);
  const [scope, setScope] = useState<"all" | "published">("all");
  const classroom = classes.data?.items.find((c) => c.id === classId) ?? classes.data?.items[0];
  const period = periodId ?? classroom?.periods[0]?.id;
  const client = useQueryClient();
  const toast = useToast();

  const results = useQuery({
    queryKey: ["direction", "results", classroom?.id, period, scope],
    queryFn: () => api<Results>(`direction/classes/${classroom!.id}/results/?period=${period}&scope=${scope}`),
    enabled: !!classroom && !!period,
    placeholderData: (previous) => previous,
  });
  const publish = useMutation({
    mutationFn: () => api<{ published: number }>(`direction/classes/${classroom!.id}/publish/?period=${period}`, { method: "POST" }),
    onSuccess: ({ published }) => {
      toast(`${published} notes publiées : les parents sont prévenus.`);
      void client.invalidateQueries({ queryKey: ["direction", "release"] });
      void client.invalidateQueries({ queryKey: ["direction"] });
    },
    onError: (e) => toast(e.message, "danger"),
  });

  if (classes.isLoading) return <Spinner />;
  if (classes.error) return <main className="content"><ErrorBox error={classes.error} /></main>;
  if (!classroom) return <main className="content"><Empty title="Aucune classe cette année" /></main>;
  const data = results.data;
  const pdf = (student?: string) =>
    fileUrl(`direction/classes/${classroom.id}/bulletins.pdf?period=${period}&scope=${scope}${student ? `&student=${student}` : ""}`);

  return (
    <main className="content content-wide">
      <div className="page-head">
        <h1>Résultats et bulletins</h1>
        <p className="muted">Moyennes, rangs et bulletins calculés à partir des notes validées.</p>
      </div>
      <div className="toolbar">
        <Field label="Classe">
          <Select value={classroom.id} onChange={(e) => { setClassId(e.target.value); setPeriodId(null); }}>
            {classes.data!.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · {c.students} élèves
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Période">
          <Select value={period} onChange={(e) => setPeriodId(e.target.value)}>
            {classroom.periods.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Segmented
        label="Notes prises en compte"
        value={scope}
        onChange={setScope}
        options={[
          { value: "all", label: "Validées et publiées" },
          { value: "published", label: "Publiées seulement" },
        ]}
      />
      {period && <ReleasePanel classroom={classroom} period={period} periodName={classroom.periods.find((p) => p.id === period)?.name ?? ""} />}
      {results.isLoading && <Spinner />}
      {results.error && <ErrorBox error={results.error} />}
      {data && (
        <>
          <div className="stats">
            <Stat label="Moyenne de la classe" value={fmt(data.class_average)} />
            <Stat label="Plus forte" value={fmt(data.highest)} />
            <Stat label="Plus faible" value={fmt(data.lowest)} />
            <Stat label="Élèves classés" value={data.ranked} />
          </div>
          <div className="row wrap">
            {data.to_publish > 0 && (
              <Button icon="send" busy={publish.isPending} onClick={() => publish.mutate()}>
                {data.to_publish > 1 ? `Publier les ${data.to_publish} évaluations validées` : "Publier l'évaluation validée"}
              </Button>
            )}
            {data.ranked > 0 && (
              <JobButton
                start={() => api<{ job: string }>(`direction/classes/${classroom.id}/bulletins/?period=${period}&scope=${scope}`, { method: "POST" })}
                busyLabel={`Préparation des ${data.ranked} bulletins…`}
              >
                Bulletins de la classe (PDF)
              </JobButton>
            )}
          </div>
          {data.ranked === 0 ? (
            <Empty icon="chart" title="Pas encore de moyenne">Aucune note validée sur cette période.</Empty>
          ) : (
            <>
              <div className="list only-mobile">
                {data.students.map((s) => (
                  <div key={s.id} className="card row-between" style={{ padding: "12px 14px" }}>
                    <div className="grow">
                      <strong className="ellipsis" style={{ display: "block" }}>
                        {s.rank_label} · {s.name}
                      </strong>
                      <span className="muted small">{s.appreciation || "—"}</span>
                    </div>
                    <strong className="num" style={{ fontSize: "1.25rem" }}>{fmt(s.average)}</strong>
                    <DownloadButton url={pdf(s.id)} filename={`bulletin-${s.name}.pdf`.replace(/\s+/g, "-")} variant="ghost" className="btn-sm" busyLabel="…">
                      PDF
                    </DownloadButton>
                  </div>
                ))}
              </div>
              <div className="table-wrap only-desktop">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Rang</th>
                      <th>Élève</th>
                      <th className="n">Moyenne</th>
                      {data.subjects.map((sub) => (
                        <th key={sub.id} className="n" title={`Coefficient ${fmt(sub.coefficient)}`}>
                          {sub.name.slice(0, 12)} <span className="muted">×{fmt(sub.coefficient)}</span>
                        </th>
                      ))}
                      <th>Appréciation</th>
                      <th aria-label="Bulletin" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.students.map((s) => (
                      <tr key={s.id}>
                        <td className="nowrap">{s.rank_label}</td>
                        <td className="nowrap">{s.name}</td>
                        <td className="n"><strong>{fmt(s.average)}</strong></td>
                        {data.subjects.map((sub) => (
                          <td key={sub.id} className="n">{fmt(s.subjects[sub.id])}</td>
                        ))}
                        <td>{s.appreciation ? <Badge tone={s.average !== null && s.average >= 10 ? "success" : "danger"}>{s.appreciation}</Badge> : "—"}</td>
                        <td>
                          <DownloadButton url={pdf(s.id)} filename={`bulletin-${s.name}.pdf`.replace(/\s+/g, "-")} variant="ghost" className="btn-sm" busyLabel="…">
                            Bulletin
                          </DownloadButton>
                        </td>
                      </tr>
                    ))}
                    <tr>
                      <td />
                      <td className="muted">Moyenne de la classe</td>
                      <td className="n"><strong>{fmt(data.class_average)}</strong></td>
                      {data.subjects.map((sub) => (
                        <td key={sub.id} className="n muted">{fmt(sub.class_average)}</td>
                      ))}
                      <td colSpan={2} />
                    </tr>
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </main>
  );
}
