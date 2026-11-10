from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import DatabaseError, connection, transaction

from apps.grades.models import Grade, GradeAudit
from apps.students.models import Guardian, Student
from apps.tenancy.context import tenant_context
from apps.tenancy.models import School

from .seed_demo import SHARED_PARENT


class Command(BaseCommand):
    help = "Montre l'isolation entre écoles, sous le rôle courant. Ne modifie rien."

    def line(self, title):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{title}"))

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            self.stdout.write(f"Connecté à PostgreSQL en tant que : {cursor.fetchone()[0]}")

        a, b = School.objects.get(slug="ceg-les-pylones"), School.objects.get(slug="saint-michel")

        self.line("1. Sans contexte d'école")
        self.stdout.write(f"   Élèves visibles : {Student.objects.count()}")

        for school in (a, b):
            self.line(f"2. Dans le contexte de : {school.name}")
            with tenant_context(school.pk):
                for grade in Grade.objects.select_related("student"):
                    self.stdout.write(f"   {grade.student} : {grade.value}/20")

        self.line(f"3. {a.name} tente de toucher les notes de {b.name}")
        with tenant_context(b.pk):
            target = Grade.objects.first().pk
        with tenant_context(a.pk):
            changed = Grade.objects.filter(pk=target).update(value=20)
            self.stdout.write(f"   Modification directe : {changed} ligne touchée")
            try:
                with transaction.atomic():
                    Student.objects.update(school=b)
            except DatabaseError as exc:
                message = str(exc).splitlines()[0]
                self.stdout.write(f"   Déplacer ses élèves chez l'autre école : refusé ({message})")

        self.line("4. Un seul parent, des enfants dans deux écoles")
        parent = get_user_model().objects.get(phone=SHARED_PARENT)
        with tenant_context(user_id=parent.pk):
            for school_id in Guardian.objects.values_list("school_id", flat=True):
                with tenant_context(school_id, parent.pk):
                    for child in Student.objects.filter(guardians__user=parent):
                        self.stdout.write(f"   {child} ({School.objects.get(pk=school_id).name})")

        self.line("5. Correction d'une note publiée (annulée en fin de démonstration)")
        with tenant_context(a.pk, parent.pk):
            grade = Grade.objects.select_related("student").first()
            Grade.objects.filter(pk=grade.pk).update(status="PUBLISHED")
            Grade.objects.filter(pk=grade.pk).update(value=18)
            for entry in GradeAudit.objects.order_by("created_at"):
                self.stdout.write(
                    f"   Journal : {grade.student} {entry.old_value} -> {entry.new_value}, "
                    f"{entry.old_status} -> {entry.new_status}"
                )
            try:
                with transaction.atomic():
                    GradeAudit.objects.update(new_value=0)
            except DatabaseError as exc:
                self.stdout.write(f"   Falsifier le journal : refusé ({str(exc).splitlines()[0]})")
            transaction.set_rollback(True)
