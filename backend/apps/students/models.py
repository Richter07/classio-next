from django.conf import settings
from django.db import models

from apps.tenancy.models import TenantModel


class Student(TenantModel):
    class Sex(models.TextChoices):
        F = "F", "Féminin"
        M = "M", "Masculin"

    matricule = models.CharField(max_length=40)
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=120)
    birth_date = models.DateField()
    sex = models.CharField(max_length=1, choices=Sex, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "matricule"], name="student_unique_matricule")
        ]

    def __str__(self):
        return f"{self.last_name} {self.first_name}"


class Enrollment(TenantModel):
    """Passage d'un élève dans une classe pour une année. La promotion crée une nouvelle ligne :
    l'historique multi-années du parent n'est donc jamais réécrit."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Inscrit"
        LEFT = "LEFT", "Parti"
        PROMOTED = "PROMOTED", "Promu"
        REPEATING = "REPEATING", "Redoublant"

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="enrollments")
    classroom = models.ForeignKey(
        "academics.Classroom", on_delete=models.PROTECT, related_name="enrollments"
    )
    year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.PROTECT, related_name="enrollments"
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "year"], name="enrollment_unique_year"
            )
        ]


class Guardian(TenantModel):
    """Le parent vu par une école. Le même numéro dans deux écoles donne deux Guardian reliés au
    même User : c'est ce qui affiche tous les enfants dans un seul compte."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="guardian_profiles"
    )
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=20, help_text="Format E.164.")
    activated_at = models.DateTimeField(null=True, blank=True)
    # Conformité : trace du consentement et de la version du texte accepté.
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=20, blank=True)
    students = models.ManyToManyField(Student, through="Guardianship", related_name="guardians")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "phone"], name="guardian_unique_phone")
        ]

    def __str__(self):
        return self.full_name


class Guardianship(TenantModel):
    class Relation(models.TextChoices):
        MOTHER = "MOTHER", "Mère"
        FATHER = "FATHER", "Père"
        TUTOR = "TUTOR", "Tuteur"
        OTHER = "OTHER", "Autre"

    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    relation = models.CharField(max_length=6, choices=Relation, default=Relation.OTHER)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "guardian", "student"], name="guardianship_unique"
            )
        ]


class ImportBatch(TenantModel):
    """Import en deux temps : contrôle ligne par ligne et rapport, puis validation humaine."""

    class Kind(models.TextChoices):
        STUDENTS = "STUDENTS", "Élèves et parents"
        GRADES = "GRADES", "Notes"

    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Reçu"
        CHECKED = "CHECKED", "Contrôlé"
        APPLIED = "APPLIED", "Appliqué"
        FAILED = "FAILED", "Échec"

    kind = models.CharField(max_length=10, choices=Kind)
    status = models.CharField(max_length=10, choices=Status, default=Status.UPLOADED)
    file_key = models.CharField(max_length=255, help_text="Fichier source, à purger après usage.")
    report = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        "accounts.Membership", on_delete=models.PROTECT, related_name="+"
    )
