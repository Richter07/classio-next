from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.tenancy.models import TenantModel


class Assessment(TenantModel):
    class Kind(models.TextChoices):
        HOMEWORK = "HOMEWORK", "Devoir"
        QUIZ = "QUIZ", "Interrogation"
        EXAM = "EXAM", "Composition"

    class_subject = models.ForeignKey(
        "academics.ClassSubject", on_delete=models.PROTECT, related_name="assessments"
    )
    period = models.ForeignKey(
        "academics.Period", on_delete=models.PROTECT, related_name="assessments"
    )
    kind = models.CharField(max_length=8, choices=Kind)
    title = models.CharField(max_length=120, blank=True)
    held_on = models.DateField(null=True, blank=True)
    max_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("20"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    weight = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        indexes = [models.Index(fields=["school", "period"], name="assessment_period_idx")]


class Grade(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SUBMITTED = "SUBMITTED", "Soumise"
        VALIDATED = "VALIDATED", "Validée"
        PUBLISHED = "PUBLISHED", "Publiée"

    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="grades")
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="grades"
    )
    # Vide tant que la note n'est pas saisie : absence de note et zéro sont deux choses.
    value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_absent = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT)
    entered_by = models.ForeignKey(
        "accounts.Membership", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    # Synchronisation hors ligne : rejouer une même mutation est sans effet (idempotence),
    # et revision détecte qu'une note a changé sur le serveur entre-temps.
    client_mutation_id = models.UUIDField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "assessment", "student"], name="grade_unique_student"
            ),
            models.UniqueConstraint(
                fields=["school", "client_mutation_id"], name="grade_unique_mutation"
            ),
            models.CheckConstraint(condition=Q(value__gte=0), name="grade_value_positive"),
            models.CheckConstraint(
                condition=Q(is_absent=False) | Q(value__isnull=True),
                name="grade_absent_has_no_value",
            ),
        ]
        indexes = [models.Index(fields=["school", "student"], name="grade_student_idx")]


class GradeAudit(TenantModel):
    """Journal alimenté uniquement par un trigger PostgreSQL : aucune voie de code, même une
    requête SQL brute, ne peut modifier une note sans y laisser de trace. Le rôle applicatif
    y a seulement accès en lecture, et un trigger y interdit modification et suppression."""

    class Action(models.TextChoices):
        UPDATE = "UPDATE", "Modification"
        DELETE = "DELETE", "Suppression"

    # Pas de clés étrangères : le journal doit survivre à la note et à son auteur.
    grade_id = models.UUIDField(db_index=True)
    action = models.CharField(max_length=6, choices=Action)
    old_value = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    new_value = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    old_status = models.CharField(max_length=10)
    new_status = models.CharField(max_length=10, blank=True)
    old_is_absent = models.BooleanField()
    new_is_absent = models.BooleanField(null=True)
    actor_user_id = models.UUIDField(null=True, default=None)
    reason = models.CharField(max_length=255, blank=True)



class ReportCardTemplate(TenantModel):
    """Options structurées uniquement : jamais de HTML fourni par l'école, car WeasyPrint
    l'exécuterait côté serveur (injection de gabarit, lecture de fichiers, SSRF)."""

    name = models.CharField(max_length=80)
    is_default = models.BooleanField(default=False)
    header_lines = models.JSONField(default=list, blank=True)
    footer_text = models.CharField(max_length=255, blank=True)
    options = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school"], condition=Q(is_default=True), name="template_single_default"
            )
        ]


class ReportCard(TenantModel):
    """Bulletin figé d'un élève : snapshot conserve les chiffres publiés, qui ne bougent pas si
    un coefficient change ensuite."""

    enrollment = models.ForeignKey(
        "students.Enrollment", on_delete=models.PROTECT, related_name="report_cards"
    )
    period = models.ForeignKey(
        "academics.Period", on_delete=models.PROTECT, related_name="report_cards"
    )
    general_average = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    rank = models.PositiveSmallIntegerField(null=True)
    is_tied = models.BooleanField(default=False, help_text="Rang ex æquo.")
    class_size = models.PositiveSmallIntegerField(null=True)
    class_average = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    highest_average = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    lowest_average = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    appreciation = models.CharField(max_length=255, blank=True)
    snapshot = models.JSONField(default=dict)
    pdf_key = models.CharField(max_length=255, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "enrollment", "period"], name="report_card_unique"
            )
        ]
