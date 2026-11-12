import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../shared/api/client";
import { Icon } from "../../shared/ui/Icon";
import { Button, Field, Segmented } from "../../shared/ui/kit";
import logo from "../../shared/ui/logo.svg";
import { PasswordInput, PhoneInput } from "./ParentLogin";

type Errors = Partial<
  Record<
    "detail" | "phone" | "code" | "password" | "consent" | "confirm",
    string
  >
>;

export function Activation() {
  const [params] = useSearchParams();
  // Le consentement « l'école partage les notes de mon enfant » ne concerne que les parents.
  const [who, setWho] = useState<"parent" | "staff">(
    params.get("pour") === "personnel" ? "staff" : "parent",
  );
  const staff = who === "staff";
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);
  const [staffDone, setStaffDone] = useState(false);
  const client = useQueryClient();
  const navigate = useNavigate();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setErrors({ confirm: "Les deux mots de passe ne sont pas identiques." });
      return;
    }
    setBusy(true);
    setErrors({});
    try {
      const result = await api<{ kind: "parent" | "staff" }>("auth/activate/", {
        body: { phone, code, password, consent: !staff && consent },
      });
      if (result.kind === "parent") {
        client.setQueryData(["me"], result);
        navigate("/parent", { replace: true });
      } else setStaffDone(true);
    } catch (e) {
      if (e instanceof ApiError) {
        const body = e.body as Record<string, string[] | string>;
        const first = (key: string) =>
          Array.isArray(body[key])
            ? (body[key] as string[]).join(" ")
            : undefined;
        setErrors({
          detail: typeof body.detail === "string" ? body.detail : undefined,
          phone: first("phone"),
          code: first("code"),
          password: first("password"),
          consent: first("consent") && staff
            ? "Ce numéro est aussi celui d'un parent d'élève : confirmez avoir lu la politique de confidentialité."
            : first("consent"),
        });
        // Ce numéro est celui d'un parent : la case d'acceptation doit être visible.
        if (first("consent")) setWho("parent");
      } else setErrors({ detail: "Erreur" });
    } finally {
      setBusy(false);
    }
  }

  if (staffDone)
    return (
      <main className="auth">
        <div className="auth-card">
          <img
            className="logo"
            src={logo}
            alt="Classio"
            width={170}
            height={55}
          />
          <div className="panel">
            <div className="notice notice-info">
              <Icon name="check" />
              <p>Votre mot de passe est enregistré.</p>
            </div>
            <Link to="/ecole/connexion" className="btn btn-primary btn-block">
              Aller à l'espace du personnel
            </Link>
          </div>
        </div>
      </main>
    );

  return (
    <main className="auth">
      <div className="auth-card">
        <img
          className="logo"
          src={logo}
          alt="Classio"
          width={170}
          height={55}
        />
        <form className="panel" onSubmit={submit} noValidate>
          <Link to={staff ? "/ecole/connexion" : "/"} className="back">
            <Icon name="back" /> Retour
          </Link>
          <div className="stack-sm">
            <h1>Première connexion</h1>
            <p className="muted">
              Avec le code d'accès remis par l'école, choisissez votre mot de
              passe. Ce code ne sert qu'une fois.
            </p>
          </div>
          <Segmented
            label="Je suis"
            value={who}
            onChange={setWho}
            options={[
              { value: "parent", label: "Parent" },
              { value: "staff", label: "Personnel" },
            ]}
          />
          <Field label="Numéro de téléphone" error={errors.phone}>
            <PhoneInput value={phone} onChange={setPhone} autoFocus />
          </Field>
          <Field
            label="Code d'accès"
            hint={
              staff
                ? "8 caractères remis par la direction, par exemple K7QM-3XPA"
                : "Sur la lettre remise par l'école, par exemple K7QM-3XPA"
            }
            error={errors.code ?? errors.detail}
          >
            <input
              className="input code-input"
              style={{ letterSpacing: "0.2em", fontSize: "1.375rem" }}
              autoCapitalize="characters"
              autoCorrect="off"
              spellCheck={false}
              autoComplete="one-time-code"
              maxLength={12}
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              required
            />
          </Field>
          <Field
            label="Choisissez un mot de passe"
            hint="8 caractères au moins. Évitez votre date de naissance."
            error={errors.password}
          >
            <PasswordInput
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Retapez le mot de passe" error={errors.confirm}>
            <PasswordInput
              value={confirm}
              onChange={setConfirm}
              autoComplete="new-password"
            />
          </Field>
          {!staff && (
            <label className="consent">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              <span>
                J'ai lu la{" "}
                <Link to="/confidentialite" target="_blank">
                  politique de confidentialité
                </Link>{" "}
                : comment l'école et Classio utilisent les données de mon enfant et les miennes.
              </span>
            </label>
          )}
          {errors.consent && (
            <p className="field-error" role="alert">
              <Icon name="alert" size={16} /> {errors.consent}
            </p>
          )}
          <Button
            type="submit"
            className="btn-block"
            busy={busy}
            disabled={
              !phone ||
              code.replace(/[^A-Za-z0-9]/g, "").length < 8 ||
              password.length < 8 ||
              (!staff && !consent)
            }
          >
            Enregistrer et me connecter
          </Button>
        </form>
      </div>
    </main>
  );
}
