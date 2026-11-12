"""Ces tests tournent sur PostgreSQL, sous le rôle classio_app : ils prouvent le comportement
de la base elle-même, et non celui du code Django."""

import uuid

import pytest
from django.apps import apps
from django.db import DatabaseError, IntegrityError, connection, transaction

from apps.academics.models import Subject
from apps.accounts.models import Membership
from apps.grades.models import Grade, GradeAudit
from apps.students.models import Enrollment, Guardian, Student
from apps.tenancy import rls
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Subscription

from .conftest import as_app_role

pytestmark = pytest.mark.django_db


def tenant_models():
    return [m for m in apps.get_models() if rls.is_tenant_model(m)]


class TestCatalog:
    """Garde-fou : une nouvelle table métier sans protection fait échouer la CI."""

    def test_every_tenant_table_has_forced_rls_and_a_policy(self):
        with connection.cursor() as cursor:
            for model in tenant_models():
                table = model._meta.db_table
                cursor.execute(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
                    [table],
                )
                assert cursor.fetchone() == (True, True), table
                cursor.execute("SELECT count(*) FROM pg_policies WHERE tablename = %s", [table])
                assert cursor.fetchone()[0] >= 1, table

    def test_every_foreign_key_between_tenant_tables_is_composite(self):
        with connection.cursor() as cursor:
            for model in tenant_models():
                for field in model._meta.local_fields:
                    if field.name == "school" or not field.is_relation:
                        continue
                    if not rls.is_tenant_model(field.remote_field.model):
                        continue
                    cursor.execute(
                        """
                        SELECT count(*) FROM pg_constraint c
                        JOIN pg_class t ON t.oid = c.conrelid
                        WHERE t.relname = %s AND c.contype = 'f'
                          AND array_length(c.conkey, 1) = 2
                          AND c.conkey @> ARRAY[
                            (SELECT attnum FROM pg_attribute
                             WHERE attrelid = t.oid AND attname = 'school_id'),
                            (SELECT attnum FROM pg_attribute
                             WHERE attrelid = t.oid AND attname = %s)
                          ]::smallint[]
                        """,
                        [model._meta.db_table, field.column],
                    )
                    assert cursor.fetchone()[0] == 1, f"{model.__name__}.{field.name}"

    def test_runtime_role_cannot_bypass_rls(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", [rls.APP_ROLE]
            )
            assert cursor.fetchone() == (False, False)


class TestReadIsolation:
    def test_no_context_returns_nothing(self, school_a):
        with as_app_role():
            assert Student.objects.count() == 0
            assert Grade.objects.count() == 0

    def test_school_only_sees_its_own_rows(self, school_a, school_b):
        with as_app_role(), tenant_context(school_a["school"].pk):
            assert list(Student.objects.all()) == [school_a["student"]]
            assert not Grade.objects.filter(pk=school_b["grade"].pk).exists()

    def test_user_context_alone_opens_no_school_data(self, school_a, parent_user):
        with as_app_role(), tenant_context(user_id=parent_user.pk):
            assert Student.objects.count() == 0

    def test_context_does_not_outlive_its_block_in_an_outer_transaction(self, school_a):
        with as_app_role(), transaction.atomic():
            with tenant_context(school_a["school"].pk):
                assert Student.objects.count() == 1
            assert Student.objects.count() == 0

    def test_nested_context_restores_the_previous_school(self, school_a, school_b):
        with as_app_role(), tenant_context(school_a["school"].pk):
            with tenant_context(school_b["school"].pk):
                assert list(Student.objects.all()) == [school_b["student"]]
            assert list(Student.objects.all()) == [school_a["student"]]


class TestWriteIsolation:
    def test_cannot_insert_into_another_school(self, school_a, school_b):
        with as_app_role(), tenant_context(school_a["school"].pk):
            with pytest.raises(DatabaseError), transaction.atomic():
                Subject.objects.create(school=school_b["school"], name="Espion")

    def test_cannot_update_or_delete_another_school(self, school_a, school_b):
        with as_app_role(), tenant_context(school_a["school"].pk):
            assert Grade.objects.filter(pk=school_b["grade"].pk).update(value=20) == 0
            assert Grade.objects.filter(pk=school_b["grade"].pk)._raw_delete("default") == 0

    def test_cannot_move_a_row_to_another_school(self, school_a, school_b):
        with as_app_role(), tenant_context(school_a["school"].pk):
            with pytest.raises(DatabaseError), transaction.atomic():
                Subject.objects.update(school=school_b["school"])

    def test_bulk_create_takes_school_from_context(self, school_a):
        with as_app_role(), tenant_context(school_a["school"].pk):
            Subject.objects.bulk_create([Subject(name="SVT"), Subject(name="PCT")])
            assert Subject.objects.filter(name="SVT", school=school_a["school"]).exists()

    def test_foreign_key_cannot_cross_schools(self, school_a, school_b):
        # Ici le RLS seul ne protège pas : la vérification de clé étrangère le contourne.
        with as_app_role(), tenant_context(school_a["school"].pk):
            with pytest.raises(IntegrityError), transaction.atomic():
                Enrollment.objects.create(
                    student_id=school_b["student"].pk,
                    classroom=school_a["classroom"],
                    year=school_a["year"],
                )
                connection.check_constraints()


class TestParentAcrossSchools:
    def test_one_account_reaches_its_children_school_by_school(
        self, school_a, school_b, parent_user
    ):
        for school in (school_a, school_b):
            with tenant_context(school["school"].pk):
                guardian = Guardian.objects.create(
                    user=parent_user, full_name="Parent", phone=parent_user.phone
                )
                guardian.students.add(school["student"])

        with as_app_role(), tenant_context(user_id=parent_user.pk):
            profiles = list(Guardian.objects.values_list("school_id", flat=True))
            assert set(profiles) == {school_a["school"].pk, school_b["school"].pk}
            # Sans contexte d'école, le rattachement ne donne accès à aucun élève.
            assert Student.objects.count() == 0

            children = []
            for school_id in profiles:
                with tenant_context(school_id, parent_user.pk):
                    children += Student.objects.filter(guardians__user=parent_user)
            assert set(children) == {school_a["student"], school_b["student"]}

    def test_self_read_does_not_expose_other_users(self, school_a, parent_user):
        from apps.accounts.models import User

        other = User.objects.create_user("+2290195000001")
        with tenant_context(school_a["school"].pk):
            Membership.objects.create(user=other, role="TEACHER", full_name="Autre")
        with as_app_role(), tenant_context(user_id=parent_user.pk):
            assert Membership.objects.count() == 0


class TestPlatform:
    def test_platform_sees_subscriptions_but_never_grades(self, school_a):
        from datetime import date

        with tenant_context(school_a["school"].pk):
            Subscription.objects.create(
                plan="ESSENTIAL", starts_on=date(2026, 9, 1), ends_on=date(2027, 8, 31)
            )
        with as_app_role(), tenant_context(is_platform=True):
            assert Subscription.objects.count() == 1
            assert Grade.objects.count() == 0
            assert Student.objects.count() == 0


class TestGradeAudit:
    def test_draft_edits_are_not_logged(self, school_a):
        with tenant_context(school_a["school"].pk):
            Grade.objects.filter(pk=school_a["grade"].pk).update(value=13)
            assert GradeAudit.objects.count() == 0

    def test_every_change_after_draft_is_logged_with_its_author(self, school_a, parent_user):
        grade = school_a["grade"]
        with as_app_role(), tenant_context(school_a["school"].pk, parent_user.pk):
            Grade.objects.filter(pk=grade.pk).update(status="PUBLISHED")
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.change_reason', 'erreur copie', true)")
            Grade.objects.filter(pk=grade.pk).update(value=15)

            entry = GradeAudit.objects.order_by("created_at").last()
            assert GradeAudit.objects.count() == 2
            assert (entry.old_value, entry.new_value) == (12, 15)
            assert entry.old_status == "PUBLISHED"
            assert entry.actor_user_id == parent_user.pk
            assert entry.reason == "erreur copie"

    def test_raw_sql_cannot_escape_the_journal(self, school_a):
        grade = school_a["grade"]
        with as_app_role(), tenant_context(school_a["school"].pk):
            Grade.objects.filter(pk=grade.pk).update(status="VALIDATED")
            with connection.cursor() as cursor:
                cursor.execute("UPDATE grades_grade SET value = 19 WHERE id = %s", [grade.pk])
            assert GradeAudit.objects.filter(new_value=19).exists()

    def test_deleting_a_validated_grade_is_logged(self, school_a):
        grade = school_a["grade"]
        with as_app_role(), tenant_context(school_a["school"].pk):
            Grade.objects.filter(pk=grade.pk).update(status="VALIDATED")
            Grade.objects.filter(pk=grade.pk).delete()
            assert GradeAudit.objects.filter(action="DELETE", grade_id=grade.pk).exists()

    def test_runtime_role_cannot_forge_or_alter_the_journal(self, school_a):
        grade = school_a["grade"]
        with tenant_context(school_a["school"].pk):
            Grade.objects.filter(pk=grade.pk).update(status="VALIDATED")
        with as_app_role(), tenant_context(school_a["school"].pk):
            for attempt in (
                lambda: GradeAudit.objects.update(reason="falsifié"),
                lambda: GradeAudit.objects.all()._raw_delete("default"),
                lambda: GradeAudit.objects.create(
                    grade_id=uuid.uuid4(), action="UPDATE", old_status="X", old_is_absent=False
                ),
            ):
                with pytest.raises(DatabaseError), transaction.atomic():
                    attempt()

    def test_even_the_owner_cannot_rewrite_the_journal(self, school_a):
        with tenant_context(school_a["school"].pk):
            Grade.objects.filter(pk=school_a["grade"].pk).update(status="VALIDATED")
        with pytest.raises(DatabaseError), transaction.atomic():
            GradeAudit.objects.update(reason="falsifié")
