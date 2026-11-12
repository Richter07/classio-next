from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.tenancy.models import TenantModel


class SchoolSettings(TenantModel):
    """Règles de calcul de l'école : de la configuration, jamais du code."""

    class Rounding(models.TextChoices):
        HALF_UP = "HALF_UP", "Au plus proche"
        DOWN = "DOWN", "Par troncature"
        UP = "UP", "Par excès"

    class Formula(models.TextChoices):
        # Usage du secondaire béninois : (moyenne des interrogations + devoir 1 + devoir 2) / 3.
        BENIN = "BENIN", "Moyenne des interrogations + devoirs et compositions"
        WEIGHTED = "WEIGHTED", "Moyenne pondérée de toutes les évaluations"

    class PublicationMode(models.TextChoices):
        BY_GRADE = "BY_GRADE", "Par note"
        BY_CLASS = "BY_CLASS", "Par classe"
        BY_PERIOD = "BY_PERIOD", "Par période"

    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("20"))
    decimals = models.PositiveSmallIntegerField(default=2)
    rounding = models.CharField(max_length=8, choices=Rounding, default=Rounding.HALF_UP)
    average_formula = models.CharField(max_length=10, choices=Formula, default=Formula.BENIN)
    publication_mode = models.CharField(
        max_length=10, choices=PublicationMode, default=PublicationMode.BY_CLASS
    )
    # Ex. [{"min": 16, "label": "Très bien"}, {"min": 14, "label": "Bien"}, ...]
    appreciation_bands = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school"], name="school_settings_unique")
        ]


class AcademicYear(TenantModel):
    label = models.CharField(max_length=20, help_text="Ex. 2026-2027")
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "label"], name="year_unique_label"),
            models.UniqueConstraint(
                fields=["school"],
                condition=models.Q(is_current=True),
                name="year_single_current",
            ),
        ]

    def __str__(self):
        return self.label


class Level(TenantModel):
    name = models.CharField(max_length=40, help_text="Ex. 6e, 3e, Tle")
    rank = models.PositiveSmallIntegerField(help_text="Ordre dans le cursus.")
    next_level = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Niveau d'accueil lors de la promotion de classe.",
    )

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="level_unique_name")
        ]

    def __str__(self):
        return self.name


class Period(TenantModel):
    """Trimestre, semestre ou autre. Sans niveau, la période vaut pour toute l'école."""

    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="periods")
    level = models.ForeignKey(
        Level, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    name = models.CharField(max_length=40)
    rank = models.PositiveSmallIntegerField()
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "year", "level", "rank"],
                name="period_unique_rank",
                nulls_distinct=False,
            )
        ]

    def __str__(self):
        return self.name


class Classroom(TenantModel):
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="classrooms")
    level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name="classrooms")
    name = models.CharField(max_length=40, help_text="Ex. 6e A, Tle D")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "year", "name"], name="classroom_unique_name")
        ]

    def __str__(self):
        return self.name


class Subject(TenantModel):
    name = models.CharField(max_length=80)
    short_name = models.CharField(max_length=12, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="subject_unique_name")
        ]

    def __str__(self):
        return self.name


class LevelSubject(TenantModel):
    """Coefficient par défaut d'une matière pour un niveau."""

    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="subjects")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="+")
    coefficient = models.DecimalField(
        max_digits=4, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "level", "subject"], name="level_subject_unique"
            )
        ]


class ClassSubject(TenantModel):
    """Une matière enseignée dans une classe : c'est le périmètre de saisie de l'enseignant.
    Un coefficient vide reprend celui du niveau."""

    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="subjects")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="+")
    teacher = models.ForeignKey(
        "accounts.Membership", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="class_subjects",
    )
    coefficient = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "classroom", "subject"], name="class_subject_unique"
            )
        ]
