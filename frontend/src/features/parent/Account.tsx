import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../shared/api/client";
import { phone } from "../../shared/format";
import { useLogout, useMe } from "../../shared/session";
import { Icon } from "../../shared/ui/Icon";
import { Button, ErrorBox, Field, useToast } from "../../shared/ui/kit";
import { PasswordInput } from "../auth/ParentLogin";

export function Account() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useMutation({
    mutationFn: () => api("auth/password/", { body: { current, new: next } }),
    onSuccess: () => {
      toast("Mot de passe modifié.");
      setCurrent("");
      setNext("");
    },
  });
  const errorOf = (key: string) => (change.error as { body?: Record<string, string[]> } | null)?.body?.[key]?.join(" ") ?? null;

  return (
    <main className="content">
      <Link to="/parent" className="back">
        <Icon name="back" /> Mes enfants
      </Link>
      <div className="page-head">
        <h1>Mon compte</h1>
        {me && <p className="muted">{phone(me.phone)}</p>}
      </div>
      <form
        className="card stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          change.mutate();
        }}
      >
        <h2>Changer de mot de passe</h2>
        <Field label="Mot de passe actuel" error={errorOf("current")}>
          <PasswordInput value={current} onChange={setCurrent} autoComplete="current-password" />
        </Field>
        <Field label="Nouveau mot de passe" hint="8 caractères au moins." error={errorOf("new")}>
          <PasswordInput value={next} onChange={setNext} autoComplete="new-password" />
        </Field>
        {change.error && !errorOf("current") && !errorOf("new") && <ErrorBox error={change.error} />}
        <Button type="submit" busy={change.isPending} disabled={!current || next.length < 8}>
          Enregistrer
        </Button>
      </form>
      <Link to="/confidentialite" className="link">
        Politique de confidentialité
      </Link>
      <Button
        variant="danger"
        icon="logout"
        onClick={async () => {
          await logout();
          navigate("/connexion", { replace: true });
        }}
      >
        Me déconnecter
      </Button>
    </main>
  );
}
