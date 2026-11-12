import { Link } from "react-router-dom";
import { isDirection, isOffice, isTeacher, useMe } from "../../shared/session";
import { Icon } from "../../shared/ui/Icon";
import { Stat } from "../../shared/ui/kit";
import { useOverview } from "./StaffLayout";
import { MyClasses } from "../teacher/MyClasses";

export function StaffHome() {
  const { data: me } = useMe();
  if (!me) return null;
  const direction = isDirection(me);
  if (!direction && isTeacher(me) && !isOffice(me)) return <MyClasses />;
  return (
    <main className="content content-wide">
      <div className="page-head">
        <h1>Bonjour {me.full_name.split(" ").slice(-1)[0]}</h1>
        <p className="muted">{me.school?.name}</p>
      </div>
      {direction ? <DirectionDashboard /> : <OfficeShortcuts />}
    </main>
  );
}

function DirectionDashboard() {
  const { data } = useOverview(true);
  if (!data) return null;
  const rate = data.guardians ? Math.round((data.guardians_active / data.guardians) * 100) : 0;
  const { setup } = data;
  const missing = [
    !setup.periods && "le découpage de l'année",
    !setup.classrooms && "les classes",
    setup.unassigned > 0 && `les enseignants de ${setup.unassigned} matière${setup.unassigned > 1 ? "s" : ""}`,
  ].filter(Boolean);
  return (
    <>
      {missing.length > 0 && (
        <Link
          to={`/ecole/configuration?onglet=${!setup.periods ? "annee" : !setup.classrooms ? "classes" : "enseignants"}`}
          className="card card-link row-between"
          style={{ borderColor: "var(--warning)", background: "#fdf6e3" }}
        >
          <div className="row">
            <Icon name="alert" />
            <div>
              <strong>Terminez la configuration de l'école</strong>
              <p className="muted small">À renseigner : {missing.join(", ")}.</p>
            </div>
          </div>
          <Icon name="next" />
        </Link>
      )}
      <div className="stats">
        <Stat label="Élèves inscrits" value={data.students} sub={`${data.classrooms} classes · ${data.year}`} />
        <Stat label="Parents activés" value={`${rate} %`} sub={`${data.guardians_active} sur ${data.guardians}`} />
        <Stat label="Notes publiées" value={data.published_grades} />
        <Stat label="À traiter" value={data.to_validate + data.to_publish} sub="évaluations" />
      </div>
      <div className="list">
        <Link to="/ecole/validation" className="card card-link row-between">
          <div className="row">
            <Icon name="check" />
            <div>
              <strong>{data.to_validate} évaluation{data.to_validate > 1 ? "s" : ""} à valider</strong>
              <p className="muted small">Envoyées par les enseignants</p>
            </div>
          </div>
          <Icon name="next" />
        </Link>
        <Link to="/ecole/validation?onglet=VALIDATED" className="card card-link row-between">
          <div className="row">
            <Icon name="send" />
            <div>
              <strong>{data.to_publish} évaluation{data.to_publish > 1 ? "s" : ""} à publier</strong>
              <p className="muted small">Les parents sont prévenus à la publication</p>
            </div>
          </div>
          <Icon name="next" />
        </Link>
        <Link to="/ecole/configuration" className="card card-link row-between">
          <div className="row">
            <Icon name="edit" />
            <div>
              <strong>Configuration</strong>
              <p className="muted small">Périodes, classes, matières, coefficients, enseignants, calcul</p>
            </div>
          </div>
          <Icon name="next" />
        </Link>
        <Link to="/ecole/personnel" className="card card-link row-between">
          <div className="row">
            <Icon name="user" />
            <div>
              <strong>Personnel</strong>
              <p className="muted small">Comptes des enseignants et du secrétariat</p>
            </div>
          </div>
          <Icon name="next" />
        </Link>
        <Link to="/ecole/resultats" className="card card-link row-between">
          <div className="row">
            <Icon name="chart" />
            <div>
              <strong>Résultats et bulletins</strong>
              <p className="muted small">Classements par classe, bulletins PDF</p>
            </div>
          </div>
          <Icon name="next" />
        </Link>
      </div>
    </>
  );
}

function OfficeShortcuts() {
  return (
    <div className="list">
      <Link to="/ecole/import" className="card card-link row-between">
        <div className="row">
          <Icon name="upload" />
          <div>
            <strong>Importer une liste d'élèves</strong>
            <p className="muted small">Depuis Excel, avec contrôle ligne par ligne</p>
          </div>
        </div>
        <Icon name="next" />
      </Link>
      <Link to="/ecole/eleves" className="card card-link row-between">
        <div className="row">
          <Icon name="users" />
          <div>
            <strong>Élèves et parents</strong>
            <p className="muted small">Inscrire un élève, relancer un parent</p>
          </div>
        </div>
        <Icon name="next" />
      </Link>
    </div>
  );
}
