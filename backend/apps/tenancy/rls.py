"""SQL de durcissement multi-écoles, appelé depuis les migrations.

Trois protections se complètent :

1. RLS activé et forcé : une ligne d'une autre école n'est ni lisible ni modifiable.
2. Politique fermée par défaut : sans contexte, app_school_id() vaut NULL et rien ne correspond.
3. Clés étrangères composites (school_id, x_id) : PostgreSQL vérifie les clés étrangères EN
   CONTOURNANT le RLS. Sans elles, une note de l'école A pourrait pointer vers un élève de
   l'école B, et un code d'erreur différent révélerait qu'un identifiant existe ailleurs.
"""

import hashlib

APP_ROLE = "classio_app"

FUNCTIONS = """
CREATE FUNCTION app_school_id() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.school_id', true), '')::uuid $$;

CREATE FUNCTION app_user_id() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION app_is_platform() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT COALESCE(current_setting('app.is_platform', true), '') = 'on' $$;
"""

GRADE_AUDIT = """
CREATE FUNCTION grades_audit_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
  target grades_grade;
BEGIN
  IF TG_OP <> 'DELETE' THEN target := NEW; END IF;
  -- Le brouillon reste libre, sinon chaque frappe de l'enseignant créerait une ligne. Le suivi
  -- commence dès qu'une note quitte le brouillon, soumission comprise.
  IF TG_OP = 'UPDATE' THEN
    IF OLD.status = 'DRAFT' AND NEW.status = 'DRAFT' THEN RETURN NEW; END IF;
    IF OLD.value IS NOT DISTINCT FROM NEW.value
       AND OLD.status = NEW.status
       AND OLD.is_absent = NEW.is_absent THEN RETURN NEW; END IF;
  ELSIF OLD.status = 'DRAFT' THEN
    RETURN OLD;
  END IF;

  INSERT INTO grades_gradeaudit (
    id, school_id, created_at, updated_at, grade_id, action,
    old_value, new_value, old_status, new_status, old_is_absent, new_is_absent,
    actor_user_id, reason
  ) VALUES (
    gen_random_uuid(), OLD.school_id, clock_timestamp(), clock_timestamp(), OLD.id, TG_OP,
    OLD.value, target.value, OLD.status, COALESCE(target.status, ''),
    OLD.is_absent, target.is_absent,
    app_user_id(), COALESCE(current_setting('app.change_reason', true), '')
  );
  RETURN NULL;
END $$;

CREATE TRIGGER grades_grade_audit
  AFTER UPDATE OR DELETE ON grades_grade
  FOR EACH ROW EXECUTE FUNCTION grades_audit_change();

CREATE FUNCTION grades_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'grades_gradeaudit est en ajout seul';
END $$;

CREATE TRIGGER grades_gradeaudit_immutable
  BEFORE UPDATE OR DELETE ON grades_gradeaudit
  FOR EACH ROW EXECUTE FUNCTION grades_audit_immutable();

REVOKE ALL ON grades_gradeaudit FROM classio_app;
GRANT SELECT ON grades_gradeaudit TO classio_app;
REVOKE ALL ON FUNCTION grades_audit_change() FROM PUBLIC;
"""

# Lignes qu'un utilisateur voit hors contexte d'école : ses propres rattachements. C'est ce qui
# permet de lister ses écoles à la connexion, et d'afficher les enfants de plusieurs écoles.
SELF_READ_TABLES = {"accounts_membership", "students_guardian"}
# La plateforme gère ces tables sans jamais accéder aux données pédagogiques.
PLATFORM_TABLES = {"tenancy_subscription", "tenancy_supportgrant"}


def _constraint_name(table: str, suffix: str) -> str:
    digest = hashlib.sha256(f"{table}:{suffix}".encode()).hexdigest()[:10]
    return f"tenant_{table[:30]}_{digest}"


def _policies_sql(table: str) -> list[str]:
    sql = [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"""CREATE POLICY tenant_isolation ON {table} FOR ALL TO {APP_ROLE}
            USING (school_id = app_school_id())
            WITH CHECK (school_id = app_school_id())""",
    ]
    if table in SELF_READ_TABLES:
        sql.append(
            f"""CREATE POLICY self_read ON {table} FOR SELECT TO {APP_ROLE}
                USING (user_id = app_user_id())"""
        )
    if table in PLATFORM_TABLES:
        sql.append(
            f"""CREATE POLICY platform_manage ON {table} FOR ALL TO {APP_ROLE}
                USING (app_is_platform()) WITH CHECK (app_is_platform())"""
        )
    return sql


def is_tenant_model(model) -> bool:
    return any(f.name == "school" for f in model._meta.local_fields) and (
        model._meta.get_field("school").remote_field.model._meta.label == "tenancy.School"
    )


def harden_model(schema_editor, model) -> None:
    """Applique toutes les protections à un modèle. À appeler pour chaque nouveau TenantModel,
    après avoir durci les modèles qu'il référence."""
    table = model._meta.db_table
    schema_editor.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {_constraint_name(table, 'key')} "
        "UNIQUE (school_id, id)"
    )
    for statement in _policies_sql(table):
        schema_editor.execute(statement)


def add_composite_foreign_keys(schema_editor, model) -> None:
    table = model._meta.db_table
    for field in model._meta.local_fields:
        if not field.is_relation or field.name == "school" or not field.remote_field:
            continue
        target = field.remote_field.model
        if not is_tenant_model(target):
            continue
        name = _constraint_name(table, f"fk_{field.column}")
        schema_editor.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} "
            f"FOREIGN KEY (school_id, {field.column}) "
            f"REFERENCES {target._meta.db_table} (school_id, id) "
            "DEFERRABLE INITIALLY DEFERRED"
        )
