import Dexie, { type Table } from "dexie";

/** Une cellule de la grille saisie sur ce téléphone et pas encore confirmée par le serveur. */
export type PendingGrade = {
  key: string; // `${assessmentId}:${studentId}`
  assessmentId: string;
  studentId: string;
  value: string | null;
  isAbsent: boolean;
  mutationId: string;
  baseRevision: number;
  updatedAt: number;
  problem?: "conflict" | "locked" | "error";
  message?: string;
  serverValue?: number | null;
  serverAbsent?: boolean;
  serverRevision?: number;
};

export type CachedGrid = { assessmentId: string; data: unknown; savedAt: number };

class ClassioDb extends Dexie {
  pending!: Table<PendingGrade, string>;
  grids!: Table<CachedGrid, string>;

  constructor() {
    super("classio");
    this.version(1).stores({ pending: "&key, assessmentId", grids: "&assessmentId" });
  }
}

export const db = new ClassioDb();

export const uuid = () =>
  crypto.randomUUID?.() ??
  "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (Number(c) ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (Number(c) / 4)))).toString(16),
  );
