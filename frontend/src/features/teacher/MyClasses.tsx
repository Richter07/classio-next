import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../shared/api/client";
import { fmt, fmtDate, shortPeriod } from "../../shared/format";
import { InstallCard } from "../../shared/pwa/InstallCard";
import { Icon } from "../../shared/ui/Icon";
import { Button, Dialog, Empty, ErrorBox, Field, Input, Segmented, Select, Spinner, StateBadge } from "../../shared/ui/kit";

export type AssessmentSummary = {
  id: string; kind: string; kind_label: string; title: string; held_on: string | null; max_score: number;
  period_id: string; period: string; state: "DRAFT" | "SUBMITTED" | "VALIDATED" | "PUBLISHED"; state_label: string;
  filled: number; enrolled: number | null; average: number | null; lowest: number | null; highest: number | null;
};
type ClassSubject = {
  id: string; classroom: { id: string; name: string }; subject: string; teacher: string; enrolled: number;
  periods: { id: string; name: string; closed: boolean }[]; assessments: AssessmentSummary[];
};

export function MyClasses() {
  const query = useQuery({
    queryKey: ["teacher", "class-subjects"],
    queryFn: () => api<{ year: string | null; class_subjects: ClassSubject[] }>("teacher/class-subjects/"),
  });
  const periods = query.data?.class_subjects[0]?.periods ?? [];
  const [period, setPeriod] = useState<string | null>(null);
  // Par défaut, la première période encore ouverte : c'est là que l'on saisit.
  const current = period ?? (periods.find((p) => !p.closed) ?? periods[0])?.id ?? "";
  const closed = periods.find((p) => p.id === current)?.closed ?? false;
  const [creating, setCreating] = useState<ClassSubject | null>(null);

  return (
    <main className="content">
      <div className="page-head">
        <h1>Mes classes</h1>
        <p className="muted">Choisissez une évaluation pour saisir les notes.</p>
      </div>
      <InstallCard />
      {query.isLoading && <Spinner />}
      {query.error && <ErrorBox error={query.error} retry={() => void query.refetch()} />}
      {query.data?.class_subjects.length === 0 && (
        <Empty icon="list" title="Aucune classe attribuée">La direction ne vous a encore attribué aucune matière.</Empty>
      )}
      {periods.length > 0 && (
        <Segmented label="Période" value={current} onChange={setPeriod} options={periods.map((p) => ({ value: p.id, label: shortPeriod(p.name) + (p.closed ? " · close" : ""), fullLabel: p.name + (p.closed ? " (close)" : "") }))} />
      )}
      {closed && (
        <div className="notice notice-info">
          <Icon name="check" />
          <p>Cette période est close par la direction : on peut consulter ses évaluations, plus en créer ni en modifier.</p>
        </div>
      )}
      {query.data?.class_subjects.map((cs) => {
        const items = cs.assessments.filter((a) => a.period_id === current);
        return (
          <section key={cs.id} className="card stack-sm">
            <div className="row-between">
              <div className="grow">
                <h2 className="ellipsis">
                  {cs.classroom.name} · {cs.subject}
                </h2>
                <p className="muted small">{cs.enrolled} élèves</p>
              </div>
              {!closed && cs.periods.some((p) => !p.closed) && (
                <Button variant="secondary" className="btn-sm" icon="plus" onClick={() => setCreating(cs)}>
                  Évaluation
                </Button>
              )}
            </div>
            {items.length === 0 ? (
              <p className="muted small">Aucune évaluation sur cette période.</p>
            ) : (
              <div className="stack-sm">
                {items.map((a) => (
                  <Link key={a.id} to={`/ecole/saisie/${a.id}`} className="card card-link row-between" style={{ padding: "12px 14px" }}>
                    <div className="grow">
                      <strong className="ellipsis" style={{ display: "block" }}>
                        {a.title || a.kind_label}
                      </strong>
                      <span className="muted small">
                        {a.kind_label}
                        {a.held_on && ` · ${fmtDate(a.held_on)}`} · {a.filled}/{a.enrolled} saisies
                        {a.average !== null && ` · moy. ${fmt(a.average)}`}
                      </span>
                    </div>
                    <StateBadge state={a.state} label={a.state_label} />
                    <Icon name="next" />
                  </Link>
                ))}
              </div>
            )}
          </section>
        );
      })}
      {creating && <CreateAssessment cs={creating} period={current} onClose={() => setCreating(null)} />}
    </main>
  );
}

function CreateAssessment({ cs, period, onClose }: { cs: ClassSubject; period: string; onClose: () => void }) {
  const open = cs.periods.filter((p) => !p.closed);
  const [form, setForm] = useState({ period: open.some((p) => p.id === period) ? period : (open[0]?.id ?? ""), kind: "QUIZ", title: "", held_on: new Date().toISOString().slice(0, 10), max_score: "20" });
  const client = useQueryClient();
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: () => api<{ id: string }>(`teacher/class-subjects/${cs.id}/assessments/`, { body: form }),
    onSuccess: ({ id }) => {
      void client.invalidateQueries({ queryKey: ["teacher"] });
      navigate(`/ecole/saisie/${id}`);
    },
  });
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  return (
    <Dialog title={`Nouvelle évaluation · ${cs.classroom.name}`} open onClose={onClose}>
      <form
        className="stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Field label="Type">
          <Select value={form.kind} onChange={set("kind")}>
            <option value="QUIZ">Interrogation</option>
            <option value="HOMEWORK">Devoir</option>
            <option value="EXAM">Composition</option>
          </Select>
        </Field>
        <Field label="Intitulé" hint="Facultatif, par exemple « Interrogation 3 »">
          <Input value={form.title} onChange={set("title")} maxLength={120} />
        </Field>
        <div className="row">
          <Field label="Date">
            <Input type="date" value={form.held_on} onChange={set("held_on")} />
          </Field>
          <Field label="Noté sur">
            <Input inputMode="numeric" value={form.max_score} onChange={set("max_score")} style={{ width: 90 }} />
          </Field>
        </div>
        <Field label="Période">
          <Select value={form.period} onChange={set("period")}>
            {open.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </Field>
        {create.error && <ErrorBox error={create.error} />}
        <Button type="submit" busy={create.isPending}>
          Créer et saisir les notes
        </Button>
      </form>
    </Dialog>
  );
}
