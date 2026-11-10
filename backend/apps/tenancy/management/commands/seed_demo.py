from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.academics.models import AcademicYear, Classroom, Level, Period, Subject
from apps.grades.models import Assessment, Grade
from apps.students.models import Enrollment, Guardian, Student
from apps.tenancy.context import tenant_context
from apps.tenancy.models import School

ADMIN_PHONE = "+2290197000099"
ADMIN_PASSWORD = "classio-demo-2026"  # noqa: S105 - compte local, refusé hors DEBUG
SHARED_PARENT = "+2290197000001"

DEMO = {
    "ceg-les-pylones": ("CEG Les Pylônes", [("ADJOVI", "Koffi", "14"), ("AGBO", "Awa", "9.5")]),
    "saint-michel": ("Collège Saint-Michel", [("HOUNSA", "Marc", "16"), ("ADJOVI", "Sena", "11")]),
}


class Command(BaseCommand):
    help = "Crée deux écoles fictives et un compte d'administration (développement uniquement)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo est réservé au développement.")
        users = get_user_model()
        if not users.objects.filter(phone=ADMIN_PHONE).exists():
            users.objects.create_superuser(ADMIN_PHONE, ADMIN_PASSWORD)
        parent = users.objects.filter(phone=SHARED_PARENT).first()
        parent = parent or users.objects.create_user(SHARED_PARENT)

        for slug, (name, pupils) in DEMO.items():
            if School.objects.filter(slug=slug).exists():
                continue
            school = School.objects.create(
                name=name, slug=slug, ownership=School.Ownership.PRIVATE, city="Cotonou"
            )
            self._fill(school, pupils, parent)
        self.stdout.write(self.style.SUCCESS(f"Admin : {ADMIN_PHONE} / {ADMIN_PASSWORD}"))

    def _fill(self, school, pupils, parent):
        with tenant_context(school.pk):
            year = AcademicYear.objects.create(
                label="2026-2027", starts_on=date(2026, 9, 14), ends_on=date(2027, 7, 2),
                is_current=True,
            )
            level = Level.objects.create(name="6e", rank=1)
            classroom = Classroom.objects.create(year=year, level=level, name="6e A")
            subject = Subject.objects.create(name="Mathématiques")
            period = Period.objects.create(
                year=year, name="Trimestre 1", rank=1,
                starts_on=date(2026, 9, 14), ends_on=date(2026, 12, 18),
            )
            exam = Assessment.objects.create(
                class_subject=classroom.subjects.create(subject=subject),
                period=period, kind=Assessment.Kind.EXAM,
            )
            guardian = Guardian.objects.create(
                user=parent, full_name="Parent de démonstration", phone=parent.phone
            )
            created = []
            for index, (last, first, value) in enumerate(pupils, start=1):
                student = Student.objects.create(
                    matricule=f"{school.slug[:3].upper()}-{index:03}", last_name=last,
                    first_name=first, birth_date=date(2014, 3, index),
                )
                Enrollment.objects.create(student=student, classroom=classroom, year=year)
                Grade.objects.create(assessment=exam, student=student, value=Decimal(value))
                created.append(student)
            # Pas de Student.objects.first() : cette commande tourne sous le rôle propriétaire,
            # qui contourne le RLS et verrait les élèves de toutes les écoles.
            guardian.students.add(created[0])
