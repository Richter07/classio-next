import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useState, type FormEvent } from "react";
import { api } from "../../shared/api/client";
import { fmtDate, phone, plural } from "../../shared/format";
import { AccessCodeDialog } from "../direction/Staff";
import { Badge, Button, ButtonLink, Dialog, Empty, ErrorBox, Field, Input, JobButton, Select, Spinner, useToast } from "../../shared/ui/kit";

type Guardian = { id: string; name: string; phone: string; activated: boolean };
type Student = { id: string; matricule: string; name: string; birth_date: string; sex: string; classroom: string; guardians: Guardian[] };
type Classroom = { id: string; name: string };

export function Students() {
  const [q, setQ] = useState("");
  const [classroom, setClassroom] = useState("");
  const [adding, setAdding] = useState(false);
  const search = useDeferredValue(q);
  const classes = useQuery({ queryKey: ["office", "classrooms"], queryFn: () => api<{ items: Classroom[] }>("office/classrooms/") });
  const list = useQuery({
    queryKey: ["office", "students", search, classroom],
    queryFn: () => api<{ items: Student[] }>(`office/students/?q=${encodeURIComponent(search)}&classroom=${classroom}`),
    placeholderData: (previous) => previous,
  });
  const toast = useToast();
  const [shown, setShown] = useState<{ guardian: Guardian; access: { code: string; expires_at: string } } | null>(null);
  const issue = useMutation({
    mutationFn: (g: Guardian) =>
      api<{ code: string; expires_at: string }>(`office/guardians/${g.id}/access-code/`, { method: "POST" }).then((access) => ({ guardian: g, access })),
    onSuccess: setShown,
    onError: (e) => toast(e.message, "danger"),
  });
  const className = classes.data?.items.find((c) => c.id === classroom)?.name;

  return (
    <main className="content content-wide">
      <div className="row-between wrap">
        <div className="page-head">
          <h1>Élèves et parents</h1>
          <p className="muted">{list.data ? plural(list.data.items.length, "élève") : " "}</p>
        </div>
        <div className="row wrap">
          <ButtonLink to="/ecole/import" icon="upload">
            Importer depuis Excel
          </ButtonLink>
          <Button icon="plus" onClick={() => setAdding(true)}>
            Inscrire un élève
          </Button>
        </div>
      </div>
      <div className="toolbar">
        <Input type="search" placeholder="Rechercher un nom ou un matricule" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Rechercher" />
        <Select value={classroom} onChange={(e) => setClassroom(e.target.value)} aria-label="Classe">
          <option value="">Toutes les classes</option>
          {classes.data?.items.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </div>
      {classroom && (
        <div className="notice notice-info">
          <div className="stack-sm grow">
            <p>
              Lettres d'accès des parents de {className} qui n'ont pas encore activé leur compte : à imprimer et à remettre aux
              élèves.
            </p>
            <div>
              <JobButton
                start={() => api<{ job: string }>("office/access-letters/", { body: { classroom } })}
                busyLabel="Préparation des lettres…"
              >
                Lettres d'accès de la classe (PDF)
              </JobButton>
            </div>
          </div>
        </div>
      )}
      {list.isLoading && <Spinner />}
      {list.error && <ErrorBox error={list.error} />}
      {list.data?.items.length === 0 && <Empty icon="users" title="Aucun élève trouvé" />}
      <div className="list">
        {list.data?.items.map((s) => (
          <article key={s.id} className="card item">
            <div className="row-between">
              <div className="grow">
                <h2 className="ellipsis">{s.name}</h2>
                <p className="muted small">
                  {s.classroom} · {s.matricule} · né(e) le {fmtDate(s.birth_date)}
                </p>
              </div>
            </div>
            {s.guardians.map((g) => (
              <div key={g.id} className="row-between wrap small">
                <span>
                  {g.name} · <span className="nowrap">{phone(g.phone)}</span>
                </span>
                <span className="row wrap">
                  {g.activated ? <Badge tone="success">Compte activé</Badge> : <Badge tone="warning">Pas encore connecté</Badge>}
                  <button className="link" disabled={issue.isPending} onClick={() => issue.mutate(g)}>
                    {g.activated ? "Mot de passe oublié" : "Code d'accès"}
                  </button>
                </span>
              </div>
            ))}
          </article>
        ))}
      </div>
      {adding && <AddStudent classes={classes.data?.items ?? []} onClose={() => setAdding(false)} />}
      <AccessCodeDialog title={`Code d'accès · ${shown?.guardian.name ?? ""}`} access={shown?.access ?? null} onClose={() => setShown(null)}>
        {shown && (
          <JobButton start={() => api<{ job: string }>("office/access-letters/", { body: { guardians: [shown.guardian.id], include_activated: true } })}>
            Imprimer sa lettre
          </JobButton>
        )}
      </AccessCodeDialog>
    </main>
  );
}

function AddStudent({ classes, onClose }: { classes: Classroom[]; onClose: () => void }) {
  const [form, setForm] = useState({
    matricule: "", last_name: "", first_name: "", birth_date: "", sex: "", classroom: classes[0]?.id ?? "", guardian_name: "", guardian_phone: "",
  });
  const client = useQueryClient();
  const toast = useToast();
  // La liste des classes peut arriver après l'ouverture du formulaire : on prend la première
  // par défaut au moment de l'envoi, sinon la requête partirait sans classe.
  const classroom = form.classroom || classes[0]?.id || "";
  const save = useMutation({
    mutationFn: () => api<{ guardian_created: boolean }>("office/students/", { body: { ...form, classroom } }),
    onSuccess: ({ guardian_created }) => {
      toast(guardian_created ? "Élève inscrit. Imprimez la lettre d'accès du parent (bouton « Code d'accès »)." : "Élève inscrit et rattaché au compte existant du parent.");
      void client.invalidateQueries({ queryKey: ["office"] });
      onClose();
    },
  });
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });
  const fieldError = (key: string) => {
    const body = (save.error as { body?: Record<string, string[]> } | null)?.body;
    return body?.[key]?.[0] ?? null;
  };

  return (
    <Dialog title="Inscrire un élève" open onClose={onClose}>
      <form
        className="stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Field label="Matricule" error={fieldError("matricule")}>
          <Input value={form.matricule} onChange={set("matricule")} required />
        </Field>
        <div className="row">
          <Field label="Nom" error={fieldError("last_name")}>
            <Input value={form.last_name} onChange={set("last_name")} required />
          </Field>
          <Field label="Prénom(s)" error={fieldError("first_name")}>
            <Input value={form.first_name} onChange={set("first_name")} required />
          </Field>
        </div>
        <div className="row">
          <Field label="Date de naissance" error={fieldError("birth_date")}>
            <Input type="date" value={form.birth_date} onChange={set("birth_date")} required />
          </Field>
          <Field label="Sexe">
            <Select value={form.sex} onChange={set("sex")}>
              <option value="">—</option>
              <option value="F">F</option>
              <option value="M">M</option>
            </Select>
          </Field>
        </div>
        <Field label="Classe" error={fieldError("classroom")}>
          <Select value={classroom} onChange={set("classroom")} disabled={!classes.length}>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Nom du parent" error={fieldError("guardian_name")}>
          <Input value={form.guardian_name} onChange={set("guardian_name")} required />
        </Field>
        <Field label="Téléphone du parent" error={fieldError("guardian_phone")} hint="Si ce numéro a déjà un enfant inscrit, le même compte est utilisé.">
          <Input type="tel" inputMode="tel" value={form.guardian_phone} onChange={set("guardian_phone")} required />
        </Field>
        {save.error && <ErrorBox error={save.error} />}
        <Button type="submit" busy={save.isPending} disabled={!classroom}>
          Inscrire
        </Button>
      </form>
    </Dialog>
  );
}
