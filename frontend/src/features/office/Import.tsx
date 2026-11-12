import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "../../shared/api/client";
import { phone, plural } from "../../shared/format";
import { Icon } from "../../shared/ui/Icon";
import { Button, ButtonLink, ErrorBox, JobButton, Stat, useToast } from "../../shared/ui/kit";

type Row = { line: number; errors: string[]; data: Record<string, string> };
type Report = { id: string; total: number; valid: number; invalid: number; new_guardians: number; rows: Row[] };

export function ImportPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [done, setDone] = useState<{ students: number; guardians: number; new_guardian_ids: string[] } | null>(null);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const toast = useToast();

  const check = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<Report>("office/imports/", { form });
    },
    onSuccess: (r) => {
      setReport(r);
      setDone(null);
    },
  });
  const apply = useMutation({
    mutationFn: () => api<{ students: number; guardians: number; new_guardian_ids: string[] }>(`office/imports/${report!.id}/apply/`, { method: "POST" }),
    onSuccess: (result) => {
      setDone(result);
      setReport(null);
      toast(`${result.students} élèves importés.`);
      void client.invalidateQueries({ queryKey: ["office"] });
    },
  });

  const pick = (file?: File | null) => file && check.mutate(file);
  const errors = report?.rows.filter((r) => r.errors.length) ?? [];
  const valid = report?.rows.filter((r) => !r.errors.length) ?? [];

  return (
    <main className="content content-wide">
      <div className="page-head">
        <h1>Importer des élèves</h1>
        <p className="muted">Les parents sont créés automatiquement à partir de leur numéro de téléphone.</p>
      </div>

      <section className="card stack-sm">
        <h2>1. Préparez le fichier</h2>
        <p className="muted small">
          Utilisez notre modèle Excel : une ligne par élève. Un parent avec plusieurs enfants ? Répétez son numéro, il n'aura qu'un seul compte.
        </p>
        <div>
          <ButtonLink to={fileUrl("office/imports/template.xlsx")} icon="download" download>
            Télécharger le modèle Excel
          </ButtonLink>
        </div>
      </section>

      <section className="card stack-sm">
        <h2>2. Envoyez-le pour contrôle</h2>
        <p className="muted small">Rien n'est enregistré à cette étape : vous verrez d'abord le rapport.</p>
        <label
          className={`drop ${over ? "over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            pick(e.dataTransfer.files[0]);
          }}
        >
          <Icon name="file" size={28} />
          <strong>{check.isPending ? "Contrôle en cours…" : "Choisir un fichier .xlsx ou .csv"}</strong>
          <span className="muted small">ou déposez-le ici · 2 Mo au plus</span>
          <input
            ref={input}
            type="file"
            accept=".xlsx,.csv"
            className="visually-hidden"
            onChange={(e) => {
              pick(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </label>
        {check.error && <ErrorBox error={check.error} />}
      </section>

      {report && (
        <section className="card stack">
          <h2>3. Vérifiez le rapport</h2>
          <div className="stats">
            <Stat label="Lignes lues" value={report.total} />
            <Stat label="Prêtes à importer" value={report.valid} />
            <Stat label="À corriger" value={report.invalid} />
            <Stat label="Nouveaux parents" value={report.new_guardians} />
          </div>
          {errors.length > 0 && (
            <div className="stack-sm">
              <div className="notice notice-warning">
                <Icon name="alert" />
                <p>
                  {errors.length} ligne(s) seront ignorées. Corrigez-les dans le fichier et renvoyez-le, ou importez déjà les lignes valides.
                </p>
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Ligne</th>
                      <th>Élève</th>
                      <th>Problème</th>
                    </tr>
                  </thead>
                  <tbody>
                    {errors.map((r) => (
                      <tr key={r.line}>
                        <td className="n">{r.line}</td>
                        <td>
                          {r.data.last_name} {r.data.first_name}
                          <div className="muted small">{r.data.matricule}</div>
                        </td>
                        <td style={{ color: "var(--danger)" }}>{r.errors.join(" ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {valid.length > 0 && (
            <details>
              <summary className="link">Voir les {valid.length} ligne(s) valides</summary>
              <div className="table-wrap" style={{ marginTop: 8 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Ligne</th>
                      <th>Élève</th>
                      <th>Classe</th>
                      <th>Parent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {valid.map((r) => (
                      <tr key={r.line}>
                        <td className="n">{r.line}</td>
                        <td>
                          {r.data.last_name} {r.data.first_name}
                        </td>
                        <td>{r.data.classroom}</td>
                        <td className="nowrap">
                          {r.data.guardian_name} · {phone(r.data.guardian_phone)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
          {apply.error && <ErrorBox error={apply.error} />}
          <div className="row wrap">
            <Button icon="check" busy={apply.isPending} disabled={!report.valid} onClick={() => apply.mutate()}>
              {report.valid > 1 ? `Importer les ${report.valid} élèves valides` : report.valid === 1 ? "Importer l'élève valide" : "Aucune ligne valide à importer"}
            </Button>
            <Button variant="ghost" onClick={() => setReport(null)}>
              Annuler
            </Button>
          </div>
        </section>
      )}

      {done && (
        <div className="notice notice-info">
          <Icon name="check" />
          <div className="stack-sm">
            <strong>
              {plural(done.students, "élève importé", "élèves importés")}, {plural(done.guardians, "nouveau parent", "nouveaux parents")}.
            </strong>
            <span>Remettez à chaque nouveau parent sa lettre d'accès : elle contient le code pour sa première connexion.</span>
            {done.new_guardian_ids.length > 0 && (
              <div>
                <JobButton
                  variant="primary"
                  start={() => api<{ job: string }>("office/access-letters/", { body: { guardians: done.new_guardian_ids } })}
                  busyLabel="Préparation des lettres…"
                >
                  {done.new_guardian_ids.length > 1 ? `Imprimer les ${done.new_guardian_ids.length} lettres d'accès` : "Imprimer la lettre d'accès"}
                </JobButton>
              </div>
            )}
            <Link to="/ecole/eleves">Voir la liste des élèves</Link>
          </div>
        </div>
      )}
    </main>
  );
}
