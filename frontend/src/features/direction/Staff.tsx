import { useMe } from "../../shared/session";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../../shared/api/client";
import { fmtFullDate, phone } from "../../shared/format";
import { Badge, Button, Dialog, Empty, ErrorBox, Field, Input, Select, Spinner, useToast } from "../../shared/ui/kit";

type Member = { id: string; full_name: string; role: string; role_label: string; phone: string; is_active: boolean; activated: boolean };
type Access = { code: string; expires_at: string };

export function AccessCodeDialog({ title, access, onClose, children }: { title: string; access: Access | null; onClose: () => void; children?: React.ReactNode }) {
  const { data: me } = useMe();
  return (
    <Dialog title={title} open={!!access} onClose={onClose}>
      {access && (
        <>
          <p className="muted">À remettre en main propre : il n'est affiché qu'une fois.</p>
          <div className="code-display" aria-label="Code d'accès">
            {access.code}
          </div>
          <p className="muted small">Valable une seule fois, jusqu'au {fmtFullDate(access.expires_at)}. Tout code précédent est annulé.</p>
          <div className="notice notice-info">
            <div className="small">
              <strong>Ce que fait la personne, la première fois :</strong>
              <ol style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                <li>Ouvrir <strong>{window.location.host}/activation</strong> sur son téléphone.</li>
                <li>Saisir son numéro de téléphone et ce code.</li>
                <li>Choisir son mot de passe.</li>
              </ol>
              <p style={{ marginTop: 6 }}>
                Ensuite, elle se connecte sur <strong>{window.location.host}/ecole/connexion</strong> avec le code de l'école
                {me?.school ? <> <strong>{me.school.slug}</strong></> : null}, son numéro et son mot de passe.
              </p>
            </div>
          </div>
          {children}
          <Button onClick={onClose}>J'ai noté le code</Button>
        </>
      )}
    </Dialog>
  );
}

export function StaffPage() {
  const query = useQuery({ queryKey: ["direction", "staff"], queryFn: () => api<{ items: Member[] }>("direction/staff/") });
  const [adding, setAdding] = useState(false);
  const [shown, setShown] = useState<{ name: string; access: Access } | null>(null);
  const client = useQueryClient();
  const toast = useToast();
  const newCode = useMutation({
    mutationFn: (m: Member) => api<Access>(`direction/staff/${m.id}/access-code/`, { method: "POST" }).then((access) => ({ name: m.full_name, access })),
    onSuccess: setShown,
    onError: (e) => toast(e.message, "danger"),
  });
  const toggle = useMutation({
    mutationFn: (m: Member) => api(`direction/staff/${m.id}/active/`, { body: { is_active: !m.is_active } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["direction", "staff"] }),
    onError: (e) => toast(e.message, "danger"),
  });

  return (
    <main className="content content-wide">
      <div className="row-between wrap">
        <div className="page-head">
          <h1>Personnel</h1>
          <p className="muted">Comptes de la direction, du secrétariat et des enseignants.</p>
        </div>
        <Button icon="plus" onClick={() => setAdding(true)}>
          Ajouter une personne
        </Button>
      </div>
      {query.isLoading && <Spinner />}
      {query.error && <ErrorBox error={query.error} />}
      {query.data?.items.length === 0 && <Empty icon="users" title="Aucun compte" />}
      <div className="list">
        {query.data?.items.map((m) => (
          <article key={m.id} className="card item" style={m.is_active ? undefined : { opacity: 0.6 }}>
            <div className="row-between wrap">
              <div className="grow">
                <h2 className="ellipsis">{m.full_name}</h2>
                <p className="muted small">
                  {m.role_label} · <span className="nowrap">{phone(m.phone)}</span>
                </p>
              </div>
              {!m.is_active ? <Badge>Désactivé</Badge> : m.activated ? <Badge tone="success">Compte activé</Badge> : <Badge tone="warning">Pas encore connecté</Badge>}
            </div>
            <div className="item-actions">
              <Button className="btn-sm" variant="secondary" busy={newCode.isPending && newCode.variables?.id === m.id} onClick={() => newCode.mutate(m)}>
                {m.activated ? "Nouveau code (mot de passe oublié)" : "Nouveau code d'accès"}
              </Button>
              <Button className="btn-sm" variant={m.is_active ? "danger" : "secondary"} onClick={() => toggle.mutate(m)}>
                {m.is_active ? "Désactiver" : "Réactiver"}
              </Button>
            </div>
          </article>
        ))}
      </div>
      {adding && <AddMember onClose={() => setAdding(false)} onCreated={(name, access) => setShown(access ? { name, access } : null)} />}
      <AccessCodeDialog title={`Code d'accès · ${shown?.name ?? ""}`} access={shown?.access ?? null} onClose={() => setShown(null)} />
    </main>
  );
}

function AddMember({ onClose, onCreated }: { onClose: () => void; onCreated: (name: string, access: Access | null) => void }) {
  const [form, setForm] = useState({ full_name: "", phone: "", role: "TEACHER" });
  const client = useQueryClient();
  const toast = useToast();
  const save = useMutation({
    mutationFn: () => api<{ full_name: string; access?: Access }>("direction/staff/", { body: form }),
    onSuccess: (member) => {
      void client.invalidateQueries({ queryKey: ["direction", "staff"] });
      if (!member.access) toast("Ajouté. Cette personne a déjà un compte Classio : elle garde son mot de passe.");
      onClose();
      onCreated(member.full_name, member.access ?? null);
    },
  });
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });
  const fieldError = (key: string) => (save.error as { body?: Record<string, string[]> } | null)?.body?.[key]?.[0] ?? null;

  return (
    <Dialog title="Ajouter une personne" open onClose={onClose}>
      <form
        className="stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Field label="Nom complet" hint="Tel qu'il apparaîtra aux parents, ex. M. DOSSOU Rodrigue" error={fieldError("full_name")}>
          <Input value={form.full_name} onChange={set("full_name")} required />
        </Field>
        <Field label="Téléphone" error={fieldError("phone")}>
          <Input type="tel" inputMode="tel" value={form.phone} onChange={set("phone")} required />
        </Field>
        <Field label="Rôle">
          <Select value={form.role} onChange={set("role")}>
            <option value="TEACHER">Enseignant</option>
            <option value="SECRETARY">Secrétariat</option>
            <option value="CENSOR">Censeur</option>
            <option value="DIRECTOR">Directeur / Administrateur</option>
          </Select>
        </Field>
        {save.error && <ErrorBox error={save.error} />}
        <Button type="submit" busy={save.isPending}>
          Ajouter
        </Button>
      </form>
    </Dialog>
  );
}
