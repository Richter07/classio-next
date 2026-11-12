"""Données de démonstration (développement uniquement).

Cette commande tourne sous le rôle propriétaire, qui CONTOURNE le RLS : chaque requête doit
donc filtrer explicitement par école ou partir d'objets créés ici. Pas de .first() global.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.academics.models import (
    AcademicYear,
    Classroom,
    Level,
    LevelSubject,
    Period,
    SchoolSettings,
    Subject,
)
from apps.accounts.models import Membership
from apps.grades.models import Assessment, Grade
from apps.notifications.models import Notification
from apps.students.models import Enrollment, Guardian, Guardianship, Student
from apps.tenancy.context import tenant_context
from apps.tenancy.models import School

PASSWORD = "classio-demo-2026"  # noqa: S105 - comptes locaux, refusés hors DEBUG
SUPERADMIN = "+2290197000099"
BANDS = [{"min": 16, "label": "Très bien"}, {"min": 14, "label": "Bien"},
         {"min": 12, "label": "Assez bien"}, {"min": 10, "label": "Passable"},
         {"min": 8, "label": "Insuffisant"}, {"min": 0, "label": "Faible"}]
LAST = ["ADJOVI", "AGBO", "AHOUANDJINOU", "ASSOGBA", "AZONHOUMON", "BIO", "CHABI", "DAGBA",
        "GBAGUIDI", "HOUNKPATIN", "KIKI", "KOUTON", "LOKOSSOU", "MENSAH", "SOSSOU", "TOGBE",
        "ZINSOU", "YAROU", "ODJO", "AYENA", "GANDONOU", "AKAKPO", "SEGLA", "VODOUNON"]
FIRST = ["Koffi", "Awa", "Sèna", "Fifamè", "Mahougnon", "Ulrich", "Grâce", "Prince", "Ornella",
         "Jospin", "Carine", "Ezéchiel", "Rachida", "Moussa", "Bénédicte", "Romaric", "Nadège",
         "Ismaël", "Aurore", "Gildas", "Espérance", "Hermann", "Josiane", "Fadel"]

SCHOOLS = {
    "ceg-les-pylones": {
        "name": "CEG Les Pylônes", "city": "Cotonou", "address": "Quartier Agla",
        "phone": "+229 01 21 00 00 00", "color": "#0E5A43",
        "staff": [("+2290197000010", "DIRECTOR", "M. HOUNGBEDJI Pascal"),
                  ("+2290197000011", "SECRETARY", "Mme ZANNOU Félicité"),
                  ("+2290197000012", "TEACHER", "M. DOSSOU Rodrigue"),
                  ("+2290197000013", "TEACHER", "Mme AKPLOGAN Sylvie"),
                  ("+2290197000014", "TEACHER", "M. HOUNGBO Arnaud")],
        # (matière, coefficient, n° d'enseignant) : 1 = DOSSOU, 2 = AKPLOGAN, 3 = HOUNGBO
        "subjects": [("Français", 3, 2), ("Mathématiques", 3, 1), ("Anglais", 2, 2),
                     ("Histoire-Géographie", 2, 3), ("SVT", 2, 1), ("EPS", 1, 3)],
        "classes": [("6e", "6e A", 14), ("6e", "6e B", 12), ("5e", "5e A", 12)],
    },
    "saint-michel": {
        "name": "Collège Saint-Michel", "city": "Porto-Novo", "address": "Ouando",
        "phone": "+229 01 20 00 00 00", "color": "#1F4E8C",
        "staff": [("+2290197000020", "DIRECTOR", "Sœur AYIKOUE Marie"),
                  ("+2290197000021", "TEACHER", "M. KPADONOU Serge")],
        "subjects": [("Français", 3, 1), ("Mathématiques", 4, 1), ("Anglais", 2, 1),
                     ("Physique-Chimie", 2, 1)],
        "classes": [("4e", "4e A", 10), ("3e", "3e A", 10)],
    },
}

# Code d'activation fixe du parent 02, pour tester la première connexion (développement seulement).
DEMO_ACCESS_CODE = "PARENT26"

# Parents de démonstration : (téléphone, nom, [(école, classe, prénom, nom)])
PARENTS = [
    ("+2290197000001", "HOUNSOU Marcel", [
        ("ceg-les-pylones", "6e A", "Koffi", "HOUNSOU"),
        ("saint-michel", "3e A", "Sèna", "HOUNSOU")]),
    ("+2290197000002", "AGOSSOU Rose", [("ceg-les-pylones", "6e A", "Fifamè", "AGOSSOU")]),
]


class Command(BaseCommand):
    help = "Crée deux écoles fictives complètes, avec un compte par rôle."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo est réservé au développement.")
        users = get_user_model()
        if not users.objects.filter(phone=SUPERADMIN).exists():
            users.objects.create_superuser(SUPERADMIN, PASSWORD)
        if School.objects.filter(slug__in=SCHOOLS).exists():
            self.stdout.write("Données de démonstration déjà présentes.")
            return
        self.rng = random.Random(2026)  # noqa: S311 - données fictives
        self.phone_counter = 0
        built = {slug: self.build(slug, spec) for slug, spec in SCHOOLS.items()}
        self.parents(built)
        # Les bulletins du trimestre 1 de Saint-Michel sont publiés : le parent 01 peut voir
        # celui de Sèna. Ceux de la 5e A restent à publier par la direction.
        from apps.grades import release

        data = built["saint-michel"]
        with tenant_context(data["school"].pk):
            for classroom, _ in data["classes"].values():
                release.release(classroom, data["periods"][0], None)
        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))

    def user(self, phone, password=None):
        users = get_user_model()
        user = users.objects.filter(phone=phone).first()
        return user or users.objects.create_user(phone, password)

    def build(self, slug, spec):
        school = School.objects.create(
            name=spec["name"], slug=slug, ownership=School.Ownership.PRIVATE,
            stages=[School.Stage.MIDDLE], status=School.Status.ACTIVE, city=spec["city"],
            address=spec["address"], phone=spec["phone"], color_primary=spec["color"])
        with tenant_context(school.pk):
            SchoolSettings.objects.create(appreciation_bands=BANDS)
            year = AcademicYear.objects.create(
                label="2026-2027", starts_on=date(2026, 9, 14), ends_on=date(2027, 7, 2),
                is_current=True)
            periods = [
                Period.objects.create(year=year, name=name, rank=i, starts_on=s, ends_on=e)
                for i, (name, s, e) in enumerate([
                    ("Trimestre 1", date(2026, 9, 14), date(2026, 12, 18)),
                    ("Trimestre 2", date(2027, 1, 4), date(2027, 3, 26)),
                    ("Trimestre 3", date(2027, 4, 12), date(2027, 7, 2))], start=1)]
            staff = {}
            for phone, role, name in spec["staff"]:
                staff.setdefault(role, []).append(Membership.objects.create(
                    user=self.user(phone, PASSWORD), role=role, full_name=name))
            teachers = staff["TEACHER"]
            subjects = []
            for name, coef, teacher_index in spec["subjects"]:
                subjects.append((Subject.objects.create(name=name), Decimal(coef),
                                 teachers[(teacher_index - 1) % len(teachers)]))
            levels, classes = {}, {}
            for rank, (level_name, class_name, size) in enumerate(spec["classes"], start=1):
                if level_name not in levels:
                    levels[level_name] = Level.objects.create(name=level_name, rank=rank)
                    for subject, coef, _ in subjects:
                        LevelSubject.objects.create(level=levels[level_name], subject=subject,
                                                    coefficient=coef)
                classroom = Classroom.objects.create(year=year, level=levels[level_name],
                                                     name=class_name)
                class_subjects = [classroom.subjects.create(subject=s, teacher=t)
                                  for s, _, t in subjects]
                students = [self.student(school, classroom, year, i) for i in range(size)]
                classes[class_name] = (classroom, students)
                # Saint-Michel et la 5e A : trimestre 1 terminé, prêt pour les bulletins.
                complete = slug == "saint-michel" or class_name == "5e A"
                self.grades(class_subjects, periods[0], students, complete)
            return {"school": school, "year": year, "classes": classes, "periods": periods}

    def student(self, school, classroom, year, index, first=None, last=None):
        rng = self.rng
        count = Student.objects.filter(school=school).count()
        student = Student.objects.create(
            matricule=f"{school.slug[:3].upper()}-26{count + 1:03}",
            last_name=last or rng.choice(LAST), first_name=first or rng.choice(FIRST),
            birth_date=date(2014 - int(classroom.name[0]) + 6, 1, 1)
            + timedelta(days=rng.randrange(330)),
            sex=rng.choice("FM"))
        Enrollment.objects.create(student=student, classroom=classroom, year=year)
        # Chaque élève a un parent, comme dans une vraie école ; 40 % ont déjà activé.
        self.phone_counter += 1
        phone = f"+2290196{self.phone_counter:06d}"
        guardian = Guardian.objects.create(
            user=self.user(phone), phone=phone,
            full_name=f"{student.last_name} {rng.choice(FIRST)}",
            activated_at=timezone.now() if rng.random() < 0.4 else None)
        Guardianship.objects.create(guardian=guardian, student=student)
        return student

    def grades(self, class_subjects, period, students, complete=False):
        """Des notes à chaque étape du circuit, pour pouvoir tout tester."""
        rng, now = self.rng, timezone.now()
        level = {s.pk: rng.uniform(7, 16) for s in students}
        published = Grade.Status.PUBLISHED
        for n, cs in enumerate(class_subjects):
            plan = [(Assessment.Kind.QUIZ, "Interrogation 1", date(2026, 10, 2), published),
                    (Assessment.Kind.HOMEWORK, "Devoir 1", date(2026, 10, 16), published)]
            if complete:
                plan += [(Assessment.Kind.QUIZ, "Interrogation 2", date(2026, 10, 23), published),
                         (Assessment.Kind.QUIZ, "Interrogation 3", date(2026, 10, 30), published),
                         (Assessment.Kind.HOMEWORK, "Devoir 2", date(2026, 11, 6), published)]
            elif n == 1:
                plan.append((Assessment.Kind.HOMEWORK, "Devoir 2", date(2026, 11, 6),
                             Grade.Status.SUBMITTED))
            elif n == 4:
                plan.append((Assessment.Kind.QUIZ, "Interrogation 2", date(2026, 11, 4),
                             Grade.Status.VALIDATED))
            if n == 0 and not complete:
                plan.append((Assessment.Kind.QUIZ, "Interrogation 2", date(2026, 11, 9),
                             Grade.Status.DRAFT))
            for kind, title, held_on, status in plan:
                assessment = Assessment.objects.create(
                    class_subject=cs, period=period, kind=kind, title=title, held_on=held_on)
                for i, student in enumerate(students):
                    if status == Grade.Status.DRAFT and i >= len(students) // 2:
                        continue  # saisie à moitié faite
                    absent = rng.random() < 0.04
                    value = None if absent else Decimal(str(round(max(0, min(20, rng.gauss(
                        level[student.pk], 2.5))) * 4) / 4))
                    Grade.objects.create(
                        assessment=assessment, student=student, value=value, is_absent=absent,
                        status=status, entered_by=cs.teacher,
                        published_at=now - timedelta(days=(date(2026, 11, 11) - held_on).days)
                        if status == Grade.Status.PUBLISHED else None)

    def parents(self, built):
        from apps.accounts import access

        for index, (phone, name, children) in enumerate(PARENTS):
            # Le premier parent a déjà son compte ; le second doit l'activer avec son code.
            user = self.user(phone, PASSWORD if index == 0 else None)
            if index == 1:
                access.issue_code(user, code=DEMO_ACCESS_CODE)
            for slug, class_name, first, last in children:
                data = built[slug]
                with tenant_context(data["school"].pk):
                    classroom, students = data["classes"][class_name]
                    child = next(s for s in students
                                 if not Guardianship.objects.filter(
                                     student=s, guardian__phone__startswith="+2290197").exists())
                    for link in Guardianship.objects.filter(student=child):
                        orphan = link.guardian
                        link.delete()
                        orphan.delete()
                    child.first_name, child.last_name = first, last
                    child.save(update_fields=["first_name", "last_name"])
                    guardian = Guardian.objects.filter(
                        school=data["school"], phone=phone).first() or \
                        Guardian.objects.create(user=user, full_name=name, phone=phone)
                    Guardianship.objects.create(guardian=guardian, student=child,
                                                relation=Guardianship.Relation.FATHER
                                                if "Marcel" in name else
                                                Guardianship.Relation.MOTHER)
                    for grade in Grade.objects.filter(
                            student=child, status=Grade.Status.PUBLISHED).select_related(
                            "assessment__class_subject__subject").order_by("-published_at")[:3]:
                        Notification.objects.create(
                            guardian=guardian, student=child,
                            kind=Notification.Kind.NEW_GRADE, channel=Notification.Channel.SMS,
                            status=Notification.Status.SENT, sent_at=grade.published_at,
                            message=f"Nouvelle note pour {first} : "
                            + ("absent(e)" if grade.is_absent else f"{grade.value:g}/20")
                            + f" en {grade.assessment.class_subject.subject.name}.",
                            link=f"/parent/enfant/{data['school'].pk}/{child.pk}")
