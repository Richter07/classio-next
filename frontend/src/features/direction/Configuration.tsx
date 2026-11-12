import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../shared/api/client";
import { fmt, fmtDate } from "../../shared/format";
import { Icon } from "../../shared/ui/Icon";
import { Badge, Button, Empty, ErrorBox, Field, Input, Segmented, Select, Spinner, useToast } from "../../shared/ui/kit";

type Config = {
  year: { id: string; label: string };
  settings: {
    max_score: number; decimals: number; rounding: string; average_formula: string;
    appreciation_bands: { min: number; label: string }[]; formulas: { value: string; label: string }[];
  };
  periods: { id: string; name: string; rank: number; starts_on: string; ends_on: string; is_closed: boolean; assessments: number }[];
  levels: { id: string; name: string; rank: number; subjects: { subject: string; coefficient: number }[] }[];
  subjects: { id: string; name: string; short_name: string }[];
  classrooms: { id: string; name: string; level: string; students: number; subjects: { id: string; subject: string; teacher: string | null; coefficient: number | null }[] }[];
  teachers: { id: string; full_name: string }[];
};

type Tab = "annee" | "classes" | "matieres" | "enseignants" | "calcul";

/** Toute modification renvoie la configuration complète : l'écran reste toujours juste. */
function useConfig() {
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: ["config"], queryFn: () => api<Config>("config/") });
  const change = useMutation({
    mutationFn: ({ method, path, body }: { method: string; path: string; body?: unknown }) => api<Config>(`config/${path}`, { method, body }),
    onSuccess: (config) => {
      client.setQueryData(["config"], config);
      void client.invalidateQueries({ queryKey: ["direction", "overview"] });
    },
    onError: (e) => toast(e.message, "danger"),
  });
  const send = (method: string, path: string, body?: unknown) => change.mutateAsync({ method, path, body }).catch(() => undefined);
  return { query, send, busy: change.isPending };
}

export function Configuration() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("onglet") as Tab) || "annee";
  const { query, send } = useConfig();
  const config = query.data;

  return (
    <main className="content content-wide">
      <div className="page-head">
        <h1>Configuration de l'école</h1>
        <p className="muted">{config ? `Année ${config.year.label}` : " "}</p>
      </div>
      <Segmented
        scroll
        label="Rubrique"
        value={tab}
        onChange={(value) => setParams({ onglet: value })}
        options={[
          { value: "annee", label: "Année" },
          { value: "classes", label: "Classes" },
          { value: "matieres", label: "Matières" },
          { value: "enseignants", label: "Enseignants" },
          { value: "calcul", label: "Calcul" },
        ]}
      />
      {query.isLoading && <Spinner />}
      {query.error && <ErrorBox error={query.error} retry={() => void query.refetch()} />}
      {config && tab === "annee" && <Periods config={config} send={send} />}
      {config && tab === "classes" && <Classes config={config} send={send} />}
      {config && tab === "matieres" && <Subjects config={config} send={send} />}
      {config && tab === "enseignants" && <Teachers config={config} send={send} />}
      {config && tab === "calcul" && <Rules config={config} send={send} />}
    </main>
  );
}

type Send = (method: string, path: string, body?: unknown) => Promise<Config | undefined>;
type Section = { config: Config; send: Send };

function AddInline({ label, placeholder, onAdd, extra }: { label: string; placeholder: string; onAdd: (value: string) => Promise<unknown>; extra?: ReactNode }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="row"
      onSubmit={async (e: FormEvent) => {
        e.preventDefault();
        if (!value.trim()) return;
        setBusy(true);
        await onAdd(value.trim());
        setValue("");
        setBusy(false);
      }}
    >
      {extra}
      <Input aria-label={label} placeholder={placeholder} value={value} onChange={(e) => setValue(e.target.value)} />
      <Button type="submit" className="btn-sm" icon="plus" busy={busy} disabled={!value.trim()}>
        Ajouter
      </Button>
    </form>
  );
}

function Periods({ config, send }: Section) {
  if (config.periods.length === 0)
    return (
      <section className="card stack">
        <h2>Découpage de l'année</h2>
        <p className="muted">Choisissez le découpage de l'école. Les dates se modifient ensuite.</p>
        <div className="row wrap">
          <Button onClick={() => void send("POST", "periods/preset/", { kind: "TRIMESTER" })}>3 trimestres</Button>
          <Button variant="secondary" onClick={() => void send("POST", "periods/preset/", { kind: "SEMESTER" })}>
            2 semestres
          </Button>
        </div>
      </section>
    );
  return (
    <div className="list">
      {config.periods.map((p) => (
        <section key={p.id} className="card stack-sm">
          <div className="row-between">
            <h2>{p.name}</h2>
            {p.is_closed ? <Badge>Close</Badge> : <Badge tone="success">Ouverte</Badge>}
          </div>
          <div className="row">
            <Field label="Début">
              <Input type="date" defaultValue={p.starts_on} onBlur={(e) => e.target.value !== p.starts_on && void send("PATCH", `periods/${p.id}/`, { starts_on: e.target.value })} />
            </Field>
            <Field label="Fin">
              <Input type="date" defaultValue={p.ends_on} onBlur={(e) => e.target.value !== p.ends_on && void send("PATCH", `periods/${p.id}/`, { ends_on: e.target.value })} />
            </Field>
          </div>
          <p className="muted small">
            {p.assessments} évaluation{p.assessments > 1 ? "s" : ""} ·{" "}
            {p.is_closed ? "plus aucune note ne peut y être saisie ni envoyée." : `du ${fmtDate(p.starts_on)} au ${fmtDate(p.ends_on)}`}
          </p>
          <div>
            <Button className="btn-sm" variant={p.is_closed ? "secondary" : "danger"} onClick={() => void send("PATCH", `periods/${p.id}/`, { is_closed: !p.is_closed })}>
              {p.is_closed ? "Rouvrir la période" : "Clore la période"}
            </Button>
          </div>
        </section>
      ))}
    </div>
  );
}

function Classes({ config, send }: Section) {
  return (
    <div className="stack">
      <section className="card stack-sm">
        <h2>Niveaux</h2>
        <p className="muted small">Du premier au dernier : 6e, 5e, 4e… Les classes se créent ensuite dans chaque niveau.</p>
        <AddInline label="Nouveau niveau" placeholder="Ex. 6e" onAdd={(name) => send("POST", "levels/", { name })} />
      </section>
      {config.levels.length === 0 && <Empty icon="list" title="Aucun niveau">Ajoutez d'abord les niveaux de l'école.</Empty>}
      {config.levels.map((level) => {
        const classes = config.classrooms.filter((c) => c.level === level.id);
        return (
          <section key={level.id} className="card stack-sm">
            <div className="row-between">
              <h2>{level.name}</h2>
              {classes.length === 0 && (
                <button className="link small" onClick={() => void send("DELETE", `levels/${level.id}/`)}>
                  Supprimer le niveau
                </button>
              )}
            </div>
            {classes.map((c) => (
              <div key={c.id} className="row-between small">
                <span>
                  <strong>{c.name}</strong> · {c.students} élève{c.students > 1 ? "s" : ""} · {c.subjects.length} matière{c.subjects.length > 1 ? "s" : ""}
                </span>
                {c.students === 0 && (
                  <button className="icon-btn" aria-label={`Supprimer ${c.name}`} onClick={() => void send("DELETE", `classrooms/${c.id}/`)}>
                    <Icon name="x" size={18} />
                  </button>
                )}
              </div>
            ))}
            <AddInline label={`Nouvelle classe en ${level.name}`} placeholder={`Ex. ${level.name} A`} onAdd={(name) => send("POST", "classrooms/", { name, level: level.id })} />
          </section>
        );
      })}
    </div>
  );
}

function Subjects({ config, send }: Section) {
  const coefficient = (levelId: string, subjectId: string) =>
    config.levels.find((l) => l.id === levelId)?.subjects.find((s) => s.subject === subjectId)?.coefficient;
  return (
    <div className="stack">
      <section className="card stack-sm">
        <h2>Matières de l'école</h2>
        <div className="row wrap">
          {config.subjects.map((s) => (
            <span key={s.id} className="badge badge-neutral" style={{ padding: "6px 6px 6px 12px" }}>
              {s.name}
              <button className="icon-btn" style={{ width: 28, height: 28 }} aria-label={`Supprimer ${s.name}`} onClick={() => void send("DELETE", `subjects/${s.id}/`)}>
                <Icon name="x" size={14} />
              </button>
            </span>
          ))}
        </div>
        <AddInline label="Nouvelle matière" placeholder="Ex. Mathématiques" onAdd={(name) => send("POST", "subjects/", { name })} />
      </section>
      {config.levels.length > 0 && config.subjects.length > 0 && (
        <p className="muted small">
          Coefficient de chaque matière par niveau. Laissez vide si la matière n'est pas enseignée à ce niveau : elle s'ajoute ou
          se retire alors dans toutes les classes du niveau.
        </p>
      )}
      {config.levels.map((level) => (
        <section key={level.id} className="card stack-sm">
          <h2>{level.name}</h2>
          {config.subjects.map((s) => {
            const value = coefficient(level.id, s.id);
            return (
              <label key={s.id} className="row-between">
                <span className={value ? "" : "muted"}>{s.name}</span>
                <Input
                  key={`${s.id}-${value ?? ""}`}
                  aria-label={`Coefficient de ${s.name} en ${level.name}`}
                  inputMode="decimal"
                  placeholder="—"
                  defaultValue={value === undefined ? "" : String(value).replace(".", ",")}
                  style={{ width: 84, textAlign: "center" }}
                  onBlur={(e) => {
                    const raw = e.target.value.trim().replace(",", ".");
                    const next = raw === "" ? null : raw;
                    if ((next === null && value === undefined) || Number(next) === value) return;
                    void send("PUT", `levels/${level.id}/subjects/${s.id}/`, { coefficient: next });
                  }}
                />
              </label>
            );
          })}
        </section>
      ))}
    </div>
  );
}

function Teachers({ config, send }: Section) {
  const subjectName = (id: string) => config.subjects.find((s) => s.id === id)?.name ?? "";
  const unassigned = config.classrooms.reduce((n, c) => n + c.subjects.filter((s) => !s.teacher).length, 0);
  if (config.teachers.length === 0)
    return (
      <Empty icon="user" title="Aucun enseignant">
        Ajoutez d'abord les enseignants dans <Link to="/ecole/personnel">Personnel</Link>.
      </Empty>
    );
  return (
    <div className="stack">
      {unassigned > 0 && (
        <div className="notice notice-warning">
          <Icon name="alert" />
          <p>
            {unassigned} matière{unassigned > 1 ? "s" : ""} sans enseignant : personne ne peut y saisir de notes.
          </p>
        </div>
      )}
      {config.classrooms.length === 0 && <Empty icon="list" title="Aucune classe">Créez d'abord les classes.</Empty>}
      {config.classrooms.map((c) => (
        <section key={c.id} className="card stack-sm">
          <h2>{c.name}</h2>
          {c.subjects.length === 0 && <p className="muted small">Aucune matière : renseignez les coefficients du niveau.</p>}
          {[...c.subjects]
            .sort((a, b) => subjectName(a.subject).localeCompare(subjectName(b.subject)))
            .map((cs) => (
              <label key={cs.id} className="assign-row">
                <span>{subjectName(cs.subject)}</span>
                <Select
                  aria-label={`Enseignant de ${subjectName(cs.subject)} en ${c.name}`}
                  value={cs.teacher ?? ""}
                  onChange={(e) => void send("PATCH", `class-subjects/${cs.id}/`, { teacher: e.target.value || null })}
                >
                  <option value="">— À attribuer —</option>
                  {config.teachers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.full_name}
                    </option>
                  ))}
                </Select>
              </label>
            ))}
        </section>
      ))}
    </div>
  );
}

function Rules({ config, send }: Section) {
  const s = config.settings;
  const [bands, setBands] = useState(s.appreciation_bands.map((b) => ({ min: String(b.min).replace(".", ","), label: b.label })));
  return (
    <div className="stack">
      <section className="card stack-sm">
        <h2>Moyenne d'une matière</h2>
        {s.formulas.map((f) => (
          <label key={f.value} className="consent">
            <input type="radio" name="formula" checked={s.average_formula === f.value} onChange={() => void send("PATCH", "settings/", { average_formula: f.value })} />
            <span>
              <strong>{f.label}</strong>
              <br />
              <span className="muted small">
                {f.value === "BENIN"
                  ? "Ex. interrogations 10 et 14, devoirs 9 et 15 : (12 + 9 + 15) / 3 = 12."
                  : "Chaque évaluation compte selon son poids, interrogations comprises."}
              </span>
            </span>
          </label>
        ))}
        <p className="notice notice-warning small">
          <Icon name="alert" size={18} /> Vérifiez sur un de vos bulletins que le résultat est identique avant la première publication.
        </p>
      </section>
      <section className="card stack-sm">
        <h2>Barème et arrondi</h2>
        <div className="row wrap">
          <Field label="Noté sur">
            <Input inputMode="numeric" defaultValue={fmt(s.max_score)} style={{ width: 90 }} onBlur={(e) => void send("PATCH", "settings/", { max_score: e.target.value.replace(",", ".") })} />
          </Field>
          <Field label="Décimales">
            <Select value={String(s.decimals)} onChange={(e) => void send("PATCH", "settings/", { decimals: Number(e.target.value) })}>
              {[0, 1, 2].map((d) => (
                <option key={d}>{d}</option>
              ))}
            </Select>
          </Field>
          <Field label="Arrondi">
            <Select value={s.rounding} onChange={(e) => void send("PATCH", "settings/", { rounding: e.target.value })}>
              <option value="HALF_UP">Au plus proche</option>
              <option value="DOWN">Par troncature</option>
              <option value="UP">Par excès</option>
            </Select>
          </Field>
        </div>
      </section>
      <section className="card stack-sm">
        <h2>Appréciations automatiques</h2>
        <p className="muted small">À partir de quelle moyenne chaque appréciation s'affiche sur le bulletin.</p>
        {bands.map((b, i) => (
          <div key={i} className="row">
            <Input aria-label="À partir de" inputMode="decimal" value={b.min} style={{ width: 80 }} onChange={(e) => setBands(bands.map((x, j) => (j === i ? { ...x, min: e.target.value } : x)))} />
            <Input aria-label="Appréciation" value={b.label} onChange={(e) => setBands(bands.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
            <button className="icon-btn" aria-label="Retirer" onClick={() => setBands(bands.filter((_, j) => j !== i))}>
              <Icon name="x" size={18} />
            </button>
          </div>
        ))}
        <div className="row wrap">
          <Button variant="ghost" className="btn-sm" icon="plus" onClick={() => setBands([...bands, { min: "", label: "" }])}>
            Ajouter
          </Button>
          <Button
            className="btn-sm"
            onClick={() =>
              void send("PATCH", "settings/", {
                appreciation_bands: bands.filter((b) => b.label.trim() && b.min !== "").map((b) => ({ min: b.min.replace(",", "."), label: b.label })),
              })
            }
          >
            Enregistrer les appréciations
          </Button>
        </div>
      </section>
    </div>
  );
}
