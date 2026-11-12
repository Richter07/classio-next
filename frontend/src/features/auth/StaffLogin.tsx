import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api, ApiError } from "../../shared/api/client";
import { useMe, type School } from "../../shared/session";
import { Button, Field, Input } from "../../shared/ui/kit";
import logo from "../../shared/ui/logo.svg";

const SCHOOL_KEY = "classio.school";

function remembered() {
  try {
    return localStorage.getItem(SCHOOL_KEY) ?? "";
  } catch {
    return "";
  }
}

export function StaffLogin() {
  const { data: me } = useMe();
  const host = useQuery({
    queryKey: ["host-school"],
    queryFn: () => api<{ school: School | null }>("auth/csrf/"),
    staleTime: Infinity,
  });
  const hostSchool = host.data?.school ?? null;
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [school, setSchool] = useState(remembered);
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const navigate = useNavigate();

  if (me?.roles.length) return <Navigate to="/ecole" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api("auth/login/", { body: { phone, password, school: hostSchool ? "" : school } });
      try {
        if (!hostSchool) localStorage.setItem(SCHOOL_KEY, school);
      } catch {
        /* stockage indisponible : sans conséquence */
      }
      client.setQueryData(["me"], result);
      navigate("/ecole", { replace: true });
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
            <h1>Espace du personnel</h1>
            <p className="muted">{hostSchool ? hostSchool.name : "Direction, secrétariat et enseignants."}</p>
          </div>
          {!hostSchool && (
            <Field label="Code de l'école" hint="Donné par la direction, par exemple ceg-les-pylones">
              <Input
                value={school}
                onChange={(e) => setSchool(e.target.value.trim().toLowerCase())}
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                required
              />
            </Field>
          )}
          <Field label="Numéro de téléphone">
            <Input type="tel" inputMode="tel" autoComplete="username" value={phone} onChange={(e) => setPhone(e.target.value)} required />
          </Field>
          <Field label="Mot de passe" error={error}>
            <div className="row">
              <Input
                type={show ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShow((s) => !s)}>
                {show ? "Masquer" : "Afficher"}
              </button>
            </div>
          </Field>
          <Button type="submit" className="btn-block" busy={busy} disabled={!phone || !password || (!hostSchool && !school)}>
            Se connecter
          </Button>
        </form>
        <div className="panel stack-sm">
          <strong>Première connexion ?</strong>
          <p className="muted small">
            La direction vous a remis un code d'accès : il sert à choisir votre mot de passe. Même chose en cas d'oubli.
          </p>
          <Link to="/activation?pour=personnel" className="btn btn-secondary btn-block">
            J'ai un code d'accès
          </Link>
        </div>
        <p className="auth-foot muted">
          Vous êtes parent ? <Link to="/connexion">Connexion des parents</Link>
        </p>
      </div>
    </main>
  );
}
