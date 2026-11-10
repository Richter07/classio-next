from django.db import migrations

from apps.tenancy import rls


def harden_all(apps, schema_editor):
    models = [m for m in apps.get_models() if rls.is_tenant_model(m)]
    for model in models:
        rls.harden_model(schema_editor, model)
    # Second passage : une clé composite exige que l'unique (school_id, id) cible existe déjà.
    for model in models:
        rls.add_composite_foreign_keys(schema_editor, model)


class Migration(migrations.Migration):
    """Irréversible à dessein : retirer l'isolation doit rester un acte explicite."""

    dependencies = [('tenancy', '0001_initial'), ('accounts', '0002_initial'), ('academics', '0002_initial'), ('students', '0001_initial'), ('grades', '0001_initial'), ('notifications', '0001_initial')]

    operations = [
        migrations.RunSQL(
            """
            GRANT USAGE ON SCHEMA public TO classio_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO classio_app;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
              GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO classio_app;
            -- Lecture seule : runserver contrôle les migrations en attente au démarrage.
            REVOKE INSERT, UPDATE, DELETE ON django_migrations FROM classio_app;
            """
        ),
        migrations.RunSQL(rls.FUNCTIONS),
        migrations.RunPython(harden_all),
        migrations.RunSQL(rls.GRADE_AUDIT),
    ]
