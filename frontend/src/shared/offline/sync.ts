import { api, ApiError } from "../api/client";
import { db, type PendingGrade } from "./db";

type Result = {
  student: string;
  mutation_id: string;
  status: "ok" | "conflict" | "locked" | "error";
  message?: string;
  value?: number | null;
  is_absent?: boolean;
  revision?: number;
};

/** Notes confirmées par le serveur, par évaluation : l'écran doit les afficher aussitôt. */
export type Confirmed = Map<string, { value: number | null; isAbsent: boolean; revision: number }>;
type Listener = (assessmentId?: string, confirmed?: Confirmed) => void;

const listeners = new Set<Listener>();
export const onSyncChange = (listener: Listener) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};
const emit = (assessmentId?: string, confirmed?: Confirmed) => listeners.forEach((l) => l(assessmentId, confirmed));

let running: Promise<void> | null = null;

/** Envoie toutes les cellules en attente. Sans réseau, elles restent sur le téléphone. */
export function syncPending(): Promise<void> {
  running ??= (async () => {
    try {
      const all = (await db.pending.toArray()).filter((p) => !p.problem);
      const byAssessment = new Map<string, PendingGrade[]>();
      for (const item of all) {
        byAssessment.set(item.assessmentId, [...(byAssessment.get(item.assessmentId) ?? []), item]);
      }
      for (const [assessmentId, items] of byAssessment) {
        const { results } = await api<{ results: Result[] }>(`assessments/${assessmentId}/grades/`, {
          body: {
            items: items.map((p) => ({
              student: p.studentId,
              value: p.isAbsent ? null : p.value,
              is_absent: p.isAbsent,
              mutation_id: p.mutationId,
              base_revision: p.baseRevision,
            })),
          },
        });
        const confirmed: Confirmed = new Map();
        await db.transaction("rw", db.pending, async () => {
          for (const r of results) {
            if (r.status === "ok")
              confirmed.set(r.student, { value: r.value ?? null, isAbsent: !!r.is_absent, revision: r.revision ?? 0 });
            const key = `${assessmentId}:${r.student}`;
            const current = await db.pending.get(key);
            if (!current || current.mutationId !== r.mutation_id) continue; // ressaisie entre-temps
            if (r.status === "ok") await db.pending.delete(key);
            else
              await db.pending.put({
                ...current,
                problem: r.status,
                message: r.message,
                serverValue: r.value,
                serverAbsent: r.is_absent,
                serverRevision: r.revision,
              });
          }
        });
        emit(assessmentId, confirmed);
      }
    } catch (error) {
      // Hors ligne ou serveur indisponible : on réessaiera. Une session expirée, elle, doit se voir.
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) throw error;
    } finally {
      running = null;
      emit();
    }
  })();
  return running;
}

let timer: ReturnType<typeof setTimeout> | undefined;
export function scheduleSync(delay = 800) {
  emit();
  clearTimeout(timer);
  timer = setTimeout(() => void syncPending(), delay);
}

let started = false;
export function startBackgroundSync() {
  if (started) return;
  started = true;
  window.addEventListener("online", () => void syncPending());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void syncPending();
  });
  setInterval(() => {
    if (navigator.onLine) void syncPending();
  }, 20_000);
}
