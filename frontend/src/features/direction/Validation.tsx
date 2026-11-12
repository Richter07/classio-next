import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../shared/api/client";
import { fmt, fmtDate } from "../../shared/format";
import { Icon } from "../../shared/ui/Icon";
import { Button, Empty, ErrorBox, Segmented, Spinner, useToast } from "../../shared/ui/kit";
import type { AssessmentSummary } from "../teacher/MyClasses";
import { useOverview } from "../staff/StaffLayout";

type Item = AssessmentSummary & { classroom: string; subject: string; teacher: string };
type Tab = "SUBMITTED" | "VALIDATED" | "PUBLISHED";

export function Validation() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("onglet") as Tab) || "SUBMITTED";
  const overview = useOverview(true);
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({
    queryKey: ["direction", "assessments", tab],
    queryFn: () => api<{ items: Item[] }>(`direction/assessments/?state=${tab}`),
  });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => api(`assessments/${id}/${action}/`, { method: "POST" }),
    onSuccess: (_, { action }) => {
      toast(action === "publish" ? "Publiées : les parents sont prévenus." : "Validées.");
      void client.invalidateQueries({ queryKey: ["direction"] });
    },
    onError: (e) => toast(e.message, "danger"),
  });

  return (
    <main className="content content-wide">
      <div className="page-head">
        <h1>Validation des notes</h1>
        <p className="muted">Contrôlez, puis publiez : les parents reçoivent la note sur leur téléphone.</p>
      </div>
      <Segmented
        label="État"
        value={tab}
        onChange={(value) => setParams({ onglet: value })}
        options={[
          { value: "SUBMITTED", label: `À valider (${overview.data?.to_validate ?? "…"})` },
          { value: "VALIDATED", label: `À publier (${overview.data?.to_publish ?? "…"})` },
          { value: "PUBLISHED", label: "Publiées" },
        ]}
      />
      {query.isLoading && <Spinner />}
      {query.error && <ErrorBox error={query.error} retry={() => void query.refetch()} />}
      {query.data?.items.length === 0 && (
        <Empty icon="check" title="Rien en attente">
          {tab === "SUBMITTED" ? "Aucune évaluation envoyée par les enseignants." : tab === "VALIDATED" ? "Aucune note validée en attente de publication." : "Aucune note publiée cette année."}
        </Empty>
      )}
      <div className="list">
        {query.data?.items.map((item) => (
          <article key={item.id} className="card item">
            <div className="row-between">
              <div className="grow">
                <h2 className="ellipsis">
                  {item.classroom} · {item.subject}
                </h2>
                <p className="muted small">
                  {item.title || item.kind_label} · {item.kind_label}
                  {item.held_on && ` · ${fmtDate(item.held_on)}`} · {item.teacher}
                </p>
              </div>
            </div>
            <div className="row wrap small">
              <span>
                Moyenne <strong className="num">{fmt(item.average)}</strong>
              </span>
              <span className="muted">·</span>
              <span>
                Min {fmt(item.lowest)} · Max {fmt(item.highest)}
              </span>
              <span className="muted">·</span>
              <span>
                {item.filled}/{item.enrolled} notes
              </span>
            </div>
            <div className="item-actions">
              <Link className="btn btn-secondary btn-sm" to={`/ecole/validation/${item.id}`}>
                <Icon name="list" size={18} /> Voir les notes
              </Link>
              {tab === "SUBMITTED" && (
                <Button className="btn-sm" variant="secondary" icon="check" busy={act.isPending && act.variables?.id === item.id && act.variables.action === "validate"} onClick={() => act.mutate({ id: item.id, action: "validate" })}>
                  Valider
                </Button>
              )}
              {tab !== "PUBLISHED" && (
                <Button className="btn-sm" icon="send" busy={act.isPending && act.variables?.id === item.id && act.variables.action === "publish"} onClick={() => act.mutate({ id: item.id, action: "publish" })}>
                  Publier
                </Button>
              )}
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
