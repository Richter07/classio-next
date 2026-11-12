import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../shared/api/client";
import { fmt, fmtDate } from "../../shared/format";
import { db, uuid, type PendingGrade } from "../../shared/offline/db";
import { onSyncChange, scheduleSync, syncPending } from "../../shared/offline/sync";
import { Icon } from "../../shared/ui/Icon";
import { Badge, Button, Dialog, ErrorBox, Field, Input, Spinner, StateBadge, useToast } from "../../shared/ui/kit";
import type { AssessmentSummary } from "./MyClasses";

type Row = {
  student_id: string; name: string; matricule: string; grade_id: string | null;
  value: number | null; is_absent: boolean; status: string; revision: number;
};
type Grid = {
  assessment: AssessmentSummary; classroom: string; subject: string; teacher: string;
  can_edit: boolean; can_review: boolean; rows: Row[];
};
type Parsed = { value: string | null; isAbsent: boolean; error?: string };

const ABSENT = /^(a|abs|absent|absente)\.?$/i;

function parse(raw: string, max: number): Parsed {
  const text = raw.trim();
  if (!text) return { value: null, isAbsent: false };
  if (ABSENT.test(text)) return { value: null, isAbsent: true };
  const normalized = text.replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return { value: null, isAbsent: false, error: "Note illisible" };
  const value = Number(normalized);
  if (value > max) return { value: null, isAbsent: false, error: `Supérieure au barème (${fmt(max)})` };
  return { value: normalized, isAbsent: false };
}

const shown = (value: string | number | null, absent: boolean) =>
  absent ? "abs" : value === null || value === "" ? "" : String(value).replace(".", ",");

async function loadGrid(id: string): Promise<Grid & { offline?: boolean }> {
  try {
    const grid = await api<Grid>(`assessments/${id}/`);
    await db.grids.put({ assessmentId: id, data: grid, savedAt: Date.now() });
    return grid;
  } catch (error) {
    // Hors ligne : on reprend la dernière version enregistrée sur ce téléphone.
    if (error instanceof ApiError && error.status === 0) {
      const cached = await db.grids.get(id);
      if (cached) return { ...(cached.data as Grid), offline: true };
    }
    throw error;
  }
}

export function GradeGrid() {
  const { assessmentId = "" } = useParams();
  const client = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ["grid", assessmentId], queryFn: () => loadGrid(assessmentId) });
  const grid = query.data;

  const [pending, setPending] = useState<Map<string, PendingGrade>>(new Map());
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [focused, setFocused] = useState<string | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [syncing, setSyncing] = useState(false);
  const [zeroing, setZeroing] = useState(false);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);

  const refreshPending = useCallback(async () => {
    const items = await db.pending.where("assessmentId").equals(assessmentId).toArray();
    setPending(new Map(items.map((p) => [p.studentId, p])));
  }, [assessmentId]);

  useEffect(() => {
    void refreshPending();
    const off = onSyncChange((syncedId, confirmed) => {
      // Une note confirmée quitte la file locale : la grille doit l'afficher avec sa nouvelle
      // révision, sinon la case paraît vide et la modification suivante ferait un faux conflit.
      if (syncedId === assessmentId && confirmed?.size) {
        client.setQueryData<Grid>(["grid", assessmentId], (grid) =>
          grid && {
            ...grid,
            rows: grid.rows.map((row) => {
              const c = confirmed.get(row.student_id);
              return c ? { ...row, value: c.value, is_absent: c.isAbsent, revision: c.revision } : row;
            }),
          },
        );
      }
      void refreshPending();
      setSyncing(false);
    });
    const on = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", down);
    return () => {
      off();
      window.removeEventListener("online", on);
      window.removeEventListener("offline", down);
    };
  }, [refreshPending, assessmentId, client]);

  const max = grid?.assessment.max_score ?? 20;

  const display = useCallback(
    (row: Row) => {
      if (row.student_id in drafts) return drafts[row.student_id];
      const local = pending.get(row.student_id);
      if (local) return shown(local.value, local.isAbsent);
      return shown(row.value, row.is_absent);
    },
    [drafts, pending],
  );

  const stats = useMemo(() => {
    if (!grid) return { filled: 0, average: null as number | null, invalid: 0 };
    let sum = 0;
    let count = 0;
    let filled = 0;
    for (const row of grid.rows) {
      const parsed = parse(display(row), max);
      if (parsed.error) continue;
      if (parsed.isAbsent) {
        // Une absence compte 0, comme sur le bulletin.
        filled += 1;
        count += 1;
      } else if (parsed.value !== null) {
        filled += 1;
        count += 1;
        sum += Number(parsed.value);
      }
    }
    return { filled, average: count ? sum / count : null, invalid: Object.keys(errors).length };
  }, [grid, display, max, errors]);

  async function commit(row: Row) {
    if (!(row.student_id in drafts)) return;
    const raw = drafts[row.student_id];
    const parsed = parse(raw, max);
    if (parsed.error) {
      setErrors((all) => ({ ...all, [row.student_id]: parsed.error! }));
      return;
    }
    await save(row, parsed);
  }

  /** Le clavier numérique du téléphone n'a pas de lettres : l'absence se marque d'un bouton. */
  async function toggleAbsent(row: Row) {
    const absent = display(row) === "abs";
    await save(row, { value: null, isAbsent: !absent });
  }

  async function fillZeros() {
    for (const row of grid!.rows) {
      if (display(row) === "") await save(row, { value: "0", isAbsent: false });
    }
    setZeroing(false);
  }

  async function save(row: Row, parsed: Parsed) {
    setErrors(({ [row.student_id]: _, ...rest }) => rest);
    setDrafts(({ [row.student_id]: _, ...rest }) => rest);
    const local = pending.get(row.student_id);
    const before = local ? { value: local.value, isAbsent: local.isAbsent } : { value: row.value === null ? null : String(row.value), isAbsent: row.is_absent };
    const same = before.isAbsent === parsed.isAbsent && Number(before.value ?? NaN) === Number(parsed.value ?? NaN);
    if (same || (before.value === null && parsed.value === null && before.isAbsent === parsed.isAbsent)) return;
    await db.pending.put({
      key: `${assessmentId}:${row.student_id}`,
      assessmentId,
      studentId: row.student_id,
      value: parsed.value,
      isAbsent: parsed.isAbsent,
      mutationId: uuid(),
      baseRevision: local?.baseRevision ?? row.revision,
      updatedAt: Date.now(),
    });
    await refreshPending();
    setSyncing(true);
    scheduleSync();
  }

  function move(index: number, delta: number) {
    const next = inputs.current[index + delta];
    if (next) {
      next.focus();
      next.select();
    }
  }

  async function resolve(item: PendingGrade, keepMine: boolean) {
    if (keepMine) {
      await db.pending.put({ ...item, problem: undefined, message: undefined, mutationId: uuid(), baseRevision: item.serverRevision ?? item.baseRevision });
      scheduleSync(0);
    } else {
      await db.pending.delete(item.key);
      await query.refetch();
    }
    await refreshPending();
  }

  const submit = useMutation({
    mutationFn: async () => {
      await syncPending();
      const left = await db.pending.where("assessmentId").equals(assessmentId).count();
      if (left) throw new Error("Des notes ne sont pas encore envoyées. Vérifiez votre connexion.");
      return api(`assessments/${assessmentId}/submit/`, { method: "POST" });
    },
    onSuccess: () => {
      toast("Notes envoyées à la direction.");
      void client.invalidateQueries({ queryKey: ["teacher"] });
      void query.refetch();
    },
    onError: (e) => toast(e.message, "danger"),
  });

  if (query.isLoading) return <Spinner />;
  if (query.error || !grid) return <main className="content"><ErrorBox error={query.error} retry={() => void query.refetch()} /></main>;

  const a = grid.assessment;
  const problems = [...pending.values()].filter((p) => p.problem);
  const waiting = pending.size - problems.length;
  const missing = grid.rows.length - stats.filled;
  const editable = grid.can_edit;

  return (
    <main className="content grid-page">
      <Link to={grid.can_review && !grid.can_edit ? "/ecole/validation" : "/ecole/saisie"} className="back">
        <Icon name="back" /> {grid.can_review && !grid.can_edit ? "Validation" : "Mes classes"}
      </Link>
      <div className="page-head">
        <div className="row-between">
          <h1 className="grow">{a.title || a.kind_label}</h1>
          <StateBadge state={a.state} label={a.state_label} />
        </div>
        <p className="muted">
          {grid.classroom} · {grid.subject} · {a.period}
          {a.held_on && ` · ${fmtDate(a.held_on)}`} · noté sur {fmt(a.max_score)}
          {grid.can_review && grid.teacher && ` · ${grid.teacher}`}
        </p>
      </div>

      {grid.can_edit && (
        <SyncStatus online={online} waiting={waiting} problems={problems.length} syncing={syncing} offline={!!grid.offline} />
      )}
      {!grid.can_edit && !grid.can_review && (
        <div className="notice notice-info">
          <Icon name="check" />
          <p>Ces notes ont été envoyées à la direction. Pour une correction, adressez-vous à elle.</p>
        </div>
      )}
      {grid.can_edit && (
        <p className="muted small">
          Tapez la note puis « Suivant » (virgule ou point acceptés). Bouton « Abs » pour un élève absent : l'absence compte
          0 dans la moyenne. Aucun élève ne peut rester sans note.
        </p>
      )}

      <ol className={`grade-grid ${editable ? "editable" : ""}`}>
        {grid.rows.map((row, index) => {
          const local = pending.get(row.student_id);
          const error = errors[row.student_id];
          return (
            <li key={row.student_id} className={`grade-row ${focused === row.student_id ? "focused" : ""} ${error ? "invalid" : ""}`}>
              <span className="index">{index + 1}</span>
              <div className="who">
                <strong>{row.name}</strong>
                {error ? (
                  <span className="msg msg-danger">{error}</span>
                ) : local?.problem ? (
                  <span className="msg msg-warning">
                    {local.message}{" "}
                    {local.problem === "conflict" && (
                      <>
                        Serveur : {shown(local.serverValue ?? null, !!local.serverAbsent) || "vide"} ·{" "}
                        <button className="link" onClick={() => void resolve(local, true)}>garder la mienne</button> ·{" "}
                        <button className="link" onClick={() => void resolve(local, false)}>prendre celle-ci</button>
                      </>
                    )}
                    {local.problem !== "conflict" && <button className="link" onClick={() => void resolve(local, false)}>annuler</button>}
                  </span>
                ) : (
                  <span>
                    {row.matricule}
                    {local && " · enregistrée sur ce téléphone"}
                  </span>
                )}
              </div>
              {editable ? (
                <input
                  ref={(el) => {
                    inputs.current[index] = el;
                  }}
                  className={`input grade-cell ${display(row) === "abs" ? "absent" : ""} ${error ? "error" : ""}`}
                  inputMode="decimal"
                  enterKeyHint={index === grid.rows.length - 1 ? "done" : "next"}
                  autoComplete="off"
                  aria-label={`Note de ${row.name}`}
                  aria-invalid={!!error}
                  value={display(row)}
                  onFocus={(e) => {
                    setFocused(row.student_id);
                    e.target.select();
                  }}
                  onChange={(e) => setDrafts((all) => ({ ...all, [row.student_id]: e.target.value }))}
                  onBlur={() => {
                    setFocused(null);
                    void commit(row);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === "ArrowDown") {
                      e.preventDefault();
                      move(index, 1);
                    } else if (e.key === "ArrowUp") {
                      e.preventDefault();
                      move(index, -1);
                    }
                  }}
                />
              ) : null}
              {editable && (
                <button
                  type="button"
                  className={`abs-btn ${display(row) === "abs" ? "on" : ""}`}
                  aria-pressed={display(row) === "abs"}
                  aria-label={`${row.name} absent(e)`}
                  onClick={() => void toggleAbsent(row)}
                >
                  Abs
                </button>
              )}
              {editable ? null : (
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  <span className="grade-static">{row.is_absent ? <Badge>Absent</Badge> : fmt(row.value)}</span>
                  {grid.can_review && row.grade_id && row.status !== "DRAFT" && (
                    <CorrectButton row={row} max={max} onDone={() => void query.refetch()} />
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <div className="grid-footer">
        <div className="grid-footer-inner">
          <div className="row-between small">
            <span>
              Moyenne <strong className="num">{fmt(stats.average)}</strong>
            </span>
            <span className={missing ? "muted" : ""}>
              {stats.filled}/{grid.rows.length} saisies
              {grid.can_edit && missing > 0 && stats.invalid === 0 && (
                <>
                  {" · "}
                  <button type="button" className="link" onClick={() => setZeroing(true)}>
                    0 aux vides
                  </button>
                </>
              )}
            </span>
          </div>
          <Dialog title="Mettre 0 aux cases vides ?" open={zeroing} onClose={() => setZeroing(false)}>
            <p>
              {missing} élève{missing > 1 ? "s" : ""} sans note recevr{missing > 1 ? "ont" : "a"} 0. Pour un élève absent, utilisez
              plutôt le bouton « Abs » : il compte aussi 0, mais le bulletin l'indique.
            </p>
            <Button onClick={() => void fillZeros()}>Mettre 0</Button>
          </Dialog>
          {grid.can_edit && (
            <Button
              icon="send"
              busy={submit.isPending}
              disabled={missing > 0 || stats.invalid > 0 || problems.length > 0}
              onClick={() => submit.mutate()}
            >
              {stats.invalid > 0
                ? `${stats.invalid} note(s) à corriger`
                : missing > 0
                  ? `Encore ${missing} élève(s) à noter`
                  : "Envoyer à la direction"}
            </Button>
          )}
          {grid.can_review && !grid.can_edit && (
            <ReviewActions grid={grid} onDone={() => { void query.refetch(); void client.invalidateQueries({ queryKey: ["direction"] }); }} navigate={navigate} />
          )}
        </div>
      </div>
    </main>
  );
}

function SyncStatus({ online, waiting, problems, syncing, offline }: { online: boolean; waiting: number; problems: number; syncing: boolean; offline: boolean }) {
  if (problems) return <div className="sync sync-error" role="status"><Icon name="alert" size={18} /> {problems} note(s) à vérifier ci-dessous</div>;
  if (!online || offline)
    return (
      <div className="sync sync-offline" role="status">
        <Icon name="offline" size={18} /> Hors ligne · {waiting} note(s) gardée(s) sur ce téléphone, envoi au retour du réseau
      </div>
    );
  if (waiting || syncing)
    return <div className="sync sync-pending" role="status"><span className="spinner" aria-hidden /> Envoi de {waiting || ""} note(s)…</div>;
  return <div className="sync sync-ok" role="status"><Icon name="check" size={18} /> Tout est enregistré</div>;
}

function ReviewActions({ grid, onDone, navigate }: { grid: Grid; onDone: () => void; navigate: (to: string) => void }) {
  const toast = useToast();
  const [returning, setReturning] = useState(false);
  const [reason, setReason] = useState("");
  const action = useMutation({
    mutationFn: (name: string) => api(`assessments/${grid.assessment.id}/${name}/`, { body: name === "return" ? { reason } : {} }),
    onSuccess: (_, name) => {
      toast(name === "publish" ? "Notes publiées : les parents sont prévenus." : name === "validate" ? "Notes validées." : "Renvoyé à l'enseignant.");
      setReturning(false);
      onDone();
      if (name !== "validate") navigate("/ecole/validation");
    },
    onError: (e) => toast(e.message, "danger"),
  });
  const state = grid.assessment.state;
  if (state === "PUBLISHED") return <p className="muted small">Publiée. Une correction se fait note par note, avec un motif.</p>;
  return (
    <div className="row wrap">
      {state === "SUBMITTED" && (
        <Button className="grow" variant="secondary" icon="check" busy={action.isPending && action.variables === "validate"} onClick={() => action.mutate("validate")}>
          Valider
        </Button>
      )}
      <Button className="grow" icon="send" busy={action.isPending && action.variables === "publish"} onClick={() => action.mutate("publish")}>
        Publier aux parents
      </Button>
      <Button variant="ghost" onClick={() => setReturning(true)}>
        Renvoyer
      </Button>
      <Dialog title="Renvoyer à l'enseignant" open={returning} onClose={() => setReturning(false)}>
        <p className="muted">Les notes repassent en brouillon : l'enseignant pourra les modifier puis les renvoyer.</p>
        <Field label="Motif, visible dans le journal">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Ex. vérifier la note de ADJOVI" />
        </Field>
        <Button variant="danger" busy={action.isPending} onClick={() => action.mutate("return")}>
          Renvoyer à l'enseignant
        </Button>
      </Dialog>
    </div>
  );
}

type HistoryEntry = { at: string; action: string; old_value: number | null; new_value: number | null; old_status: string; new_status: string; old_is_absent: boolean; new_is_absent: boolean | null; by: string; reason: string };

function CorrectButton({ row, max, onDone }: { row: Row; max: number; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(shown(row.value, row.is_absent));
  const [reason, setReason] = useState("");
  const toast = useToast();
  const client = useQueryClient();
  const history = useQuery({
    queryKey: ["history", row.grade_id],
    queryFn: () => api<{ items: HistoryEntry[] }>(`grades/${row.grade_id}/history/`),
    enabled: open,
    staleTime: 0,
  });
  const parsed = parse(value, max);
  const save = useMutation({
    mutationFn: () => api(`grades/${row.grade_id}/correct/`, { body: { value: parsed.value, is_absent: parsed.isAbsent, reason } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["history", row.grade_id] });
      toast(row.status === "PUBLISHED" ? "Note corrigée. Le parent est prévenu." : "Note corrigée.");
      setOpen(false);
      onDone();
    },
  });
  const label = (v: number | null, absent: boolean | null) => (absent ? "absent" : fmt(v));
  return (
    <>
      <button className="icon-btn" aria-label={`Corriger la note de ${row.name}`} onClick={() => setOpen(true)}>
        <Icon name="edit" size={18} />
      </button>
      <Dialog title={`Corriger · ${row.name}`} open={open} onClose={() => setOpen(false)}>
        <Field label={`Nouvelle note (sur ${fmt(max)}) ou « abs »`} error={parsed.error}>
          <Input inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} />
        </Field>
        <Field label="Motif de la correction" hint="Obligatoire. Il est conservé dans le journal.">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
        {save.error && <ErrorBox error={save.error} />}
        <Button busy={save.isPending} disabled={!!parsed.error || reason.trim().length < 3 || (!parsed.value && !parsed.isAbsent)} onClick={() => save.mutate()}>
          Enregistrer la correction
        </Button>
        <div className="stack-sm">
          <h3>Historique</h3>
          {history.data?.items.length === 0 && <p className="muted small">Aucune modification depuis l'envoi.</p>}
          {history.data?.items.map((h, i) => (
            <div key={i} className="small">
              <strong>{new Date(h.at).toLocaleString("fr-FR")}</strong> · {h.by}
              <div className="muted">
                {h.old_status} → {h.new_status} · {label(h.old_value, h.old_is_absent)} → {label(h.new_value, h.new_is_absent)}
                {h.reason && ` · « ${h.reason} »`}
              </div>
            </div>
          ))}
        </div>
      </Dialog>
    </>
  );
}
