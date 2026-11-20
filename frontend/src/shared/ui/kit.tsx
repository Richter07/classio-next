import { useNavigation } from "react-router-dom";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { Link } from "react-router-dom";
import { Icon, type IconName } from "./Icon";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  icon,
  busy,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; icon?: IconName; busy?: boolean }) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      disabled={busy || props.disabled}
      aria-busy={busy || undefined}
      {...props}
    >
      {busy ? <span className="spinner" aria-hidden /> : icon && <Icon name={icon} />}
      <span>{children}</span>
    </button>
  );
}

export function ButtonLink({
  to,
  variant = "secondary",
  icon,
  children,
  download,
}: {
  to: string;
  variant?: Variant;
  icon?: IconName;
  children: ReactNode;
  download?: boolean;
}) {
  if (download) {
    return (
      <a className={`btn btn-${variant}`} href={to} download>
        {icon && <Icon name={icon} />}
        <span>{children}</span>
      </a>
    );
  }
  return (
    <Link className={`btn btn-${variant}`} to={to}>
      {icon && <Icon name={icon} />}
      <span>{children}</span>
    </Link>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {error && (
        <span className="field-error" role="alert">
          <Icon name="alert" size={16} /> {error}
        </span>
      )}
    </label>
  );
}

export const Input = (props: InputHTMLAttributes<HTMLInputElement>) => <input className="input" {...props} />;

export const Select = (props: SelectHTMLAttributes<HTMLSelectElement>) => (
  <select className="input" {...props} />
);

export function Spinner({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden /> {label}
    </div>
  );
}

export function Empty({ icon = "list", title, children }: { icon?: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name={icon} size={28} />
      </span>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}

export function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : "Une erreur est survenue.";
  return (
    <div className="notice notice-danger" role="alert">
      <Icon name="alert" />
      <div>
        <p>{message}</p>
        {retry && (
          <button className="link" onClick={retry}>
            Réessayer
          </button>
        )}
      </div>
    </div>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "success" | "warning" | "danger" | "info"; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

const STATE_TONES = { DRAFT: "neutral", SUBMITTED: "warning", VALIDATED: "info", PUBLISHED: "success" } as const;
export const StateBadge = ({ state, label }: { state: keyof typeof STATE_TONES; label: string }) => (
  <Badge tone={STATE_TONES[state]}>{label}</Badge>
);

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  scroll,
}: {
  value: T;
  options: { value: T; label: string; fullLabel?: string }[];
  onChange: (value: T) => void;
  label: string;
  /** Onglets nombreux : la barre défile au lieu de tronquer les libellés. */
  scroll?: boolean;
}) {
  const bar = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // L'onglet actif reste visible même quand la barre défile.
    bar.current?.querySelector<HTMLElement>("[aria-selected=true]")?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [value]);
  return (
    <div ref={bar} className={`segmented ${scroll ? "segmented-scroll" : ""}`} role="tablist" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          // Dans un formulaire, un bouton sans type le soumet : changer d'onglet ne doit rien envoyer.
          type="button"
          role="tab"
          aria-selected={option.value === value}
          aria-label={option.fullLabel}
          title={option.fullLabel}
          className={option.value === value ? "active" : ""}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Dialog({
  title,
  open,
  onClose,
  children,
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className="dialog" onClose={onClose} onCancel={onClose}>
      <div className="dialog-head">
        <h2>{title}</h2>
        <button className="icon-btn" onClick={onClose} aria-label="Fermer">
          <Icon name="x" />
        </button>
      </div>
      {open && <div className="dialog-body">{children}</div>}
    </dialog>
  );
}

type Toast = { id: number; text: string; tone: "success" | "danger" };
const ToastContext = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "success") => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all, { id, text, tone }]);
    setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), 4000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            <Icon name={t.tone === "success" ? "check" : "alert"} /> {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}

async function saveBlob(response: Response, filename: string) {
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 10_000);
}

/** Document long à produire (bulletins d'une classe, lettres d'accès) : le serveur le prépare en
 *  tâche de fond, on suit son avancement puis on le télécharge. */
export function JobButton({
  start,
  children,
  busyLabel = "Préparation…",
  variant = "secondary",
  icon = "download",
  className = "",
  disabled,
}: {
  start: () => Promise<{ job: string }>;
  children: ReactNode;
  busyLabel?: string;
  variant?: Variant;
  icon?: IconName;
  className?: string;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  async function run() {
    setBusy(true);
    try {
      const { job } = await start();
      for (let i = 0; i < 400; i++) {
        const state = await (await fetch(`/api/v1/jobs/${job}/`, { credentials: "same-origin" })).json();
        if (state.status === "failed") throw new Error(state.error || "La génération a échoué.");
        if (state.status === "done") {
          const file = await fetch(`/api/v1/jobs/${job}/file/`, { credentials: "same-origin" });
          if (!file.ok) throw new Error("Document introuvable.");
          await saveBlob(file, state.filename);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      throw new Error("La préparation prend trop de temps. Réessayez plus tard.");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Erreur", "danger");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Button variant={variant} icon={icon} busy={busy} onClick={() => void run()} className={className} disabled={disabled}>
      {busy ? busyLabel : children}
    </Button>
  );
}

/** Téléchargement d'un fichier généré par le serveur, avec un état visible pendant la
 *  préparation : un bulletin peut prendre quelques secondes, l'écran ne doit pas sembler figé. */
export function DownloadButton({
  url,
  filename,
  children,
  busyLabel = "Préparation…",
  variant = "secondary",
  className = "",
}: {
  url: string;
  filename: string;
  children: ReactNode;
  busyLabel?: string;
  variant?: Variant;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  async function download() {
    setBusy(true);
    try {
      const response = await fetch(url, { credentials: "same-origin" });
      if (!response.ok) throw new Error();
      await saveBlob(response, filename);
    } catch {
      toast("Le téléchargement a échoué. Vérifiez votre connexion et réessayez.", "danger");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Button variant={variant} icon="download" busy={busy} onClick={() => void download()} className={className}>
      {busy ? busyLabel : children}
    </Button>
  );
}

/** Une page se charge à la demande : sans repère, sur réseau lent, on croit que le clic n'a rien
 *  fait. La barre apparaît dès le clic, jusqu'à l'affichage de la nouvelle page. */
export function RouteProgress() {
  const navigation = useNavigation();
  if (navigation.state !== "loading") return null;
  return <div className="route-progress" role="progressbar" aria-label="Chargement de la page" />;
}
