import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api, ApiError } from "../../shared/api/client";
import { useMe } from "../../shared/session";
import { Icon } from "../../shared/ui/Icon";
import { Button, Field } from "../../shared/ui/kit";
import logo from "../../shared/ui/logo.svg";

export function PhoneInput(props: { value: string; onChange: (value: string) => void; autoFocus?: boolean }) {
  return (
    <div className="phone-input">
      <span className="prefix" aria-hidden>
        +229
      </span>
      <input
        className="input"
        type="tel"
        inputMode="tel"
        autoComplete="username"
        placeholder="01 97 00 00 00"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        autoFocus={props.autoFocus}
        required
      />
    </div>
  );
}

export function PasswordInput(props: { value: string; onChange: (value: string) => void; autoComplete: string; id?: string }) {
  const [show, setShow] = useState(false);
  return (
    <div className="row">
      <input
        id={props.id}
        className="input"
        type={show ? "text" : "password"}
        autoComplete={props.autoComplete}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        required
      />
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShow((s) => !s)}>
        {show ? "Masquer" : "Afficher"}
      </button>
    </div>
  );
}

export function ParentLogin() {
  const { data: me } = useMe();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [forgot, setForgot] = useState(false);
  const client = useQueryClient();
  const navigate = useNavigate();
  if (me?.is_parent) return <Navigate to="/parent" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      client.setQueryData(["me"], await api("auth/parent/login/", { body: { phone, password } }));
      navigate("/parent", { replace: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <div className="auth-card">
        <img className="logo" src={logo} alt="Classio" width={170} height={55} />
        <form className="panel" onSubmit={submit} noValidate>
          <div className="stack-sm">
            <h1>Suivez les notes de vos enfants</h1>
            <p className="muted">Connectez-vous avec le numéro donné à l'école.</p>
          </div>
          <Field label="Numéro de téléphone">
            <PhoneInput value={phone} onChange={setPhone} autoFocus />
          </Field>
          <Field label="Mot de passe" error={error}>
            <PasswordInput value={password} onChange={setPassword} autoComplete="current-password" />
          </Field>
          <Button type="submit" className="btn-block" busy={busy} disabled={phone.replace(/\D/g, "").length < 8 || !password}>
            Me connecter
          </Button>
          <div className="stack-sm" style={{ textAlign: "center" }}>
            <Link to="/activation" className="btn btn-secondary btn-block">
              Première connexion : j'ai un code de l'école
            </Link>
            <button type="button" className="link" onClick={() => setForgot((f) => !f)}>
              Mot de passe oublié ?
            </button>
            {forgot && (
              <div className="notice notice-info" style={{ textAlign: "left" }}>
                <Icon name="alert" />
                <p>
                  Demandez un nouveau code au secrétariat de l'école de votre enfant, puis touchez « Première connexion » pour
                  choisir un nouveau mot de passe.
                </p>
              </div>
            )}
          </div>
        </form>
        <p className="auth-foot muted">
          Vous travaillez dans une école ? <Link to="/ecole/connexion">Espace du personnel</Link>
        </p>
      </div>
    </main>
  );
}
