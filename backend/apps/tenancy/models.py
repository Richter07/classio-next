import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.db import models

from .context import current_school_id

hex_color = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Couleur attendue au format #RRGGBB.")


class TenantForeignKey(models.ForeignKey):
    """Renseigne school_id depuis le contexte, y compris pour bulk_create (imports Excel)."""

    def pre_save(self, model_instance, add):
        if add and getattr(model_instance, self.attname) is None:
            setattr(model_instance, self.attname, current_school_id())
        return super().pre_save(model_instance, add)


class TimestampedModel(models.Model):
    # UUID : non énumérable, et générable hors ligne par le client.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class School(TimestampedModel):
    """Table globale, volontairement sans RLS : elle sert à résoudre le sous-domaine avant
    l'authentification. Elle ne contient donc que des informations publiques d'école."""

    class Ownership(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        PRIVATE = "PRIVATE", "Privé"
        FAITH = "FAITH", "Confessionnel"

    class Stage(models.TextChoices):
        PRIMARY = "PRIMARY", "Primaire"
        MIDDLE = "MIDDLE", "Collège"
        HIGH = "HIGH", "Lycée"

    class Status(models.TextChoices):
        TRIAL = "TRIAL", "Essai"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspendue"

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=63, unique=True, help_text="Sous-domaine de l'école.")
    ownership = models.CharField(max_length=10, choices=Ownership)
    # Un même établissement couvre souvent plusieurs cycles.
    stages = ArrayField(models.CharField(max_length=10, choices=Stage), default=list)
    status = models.CharField(max_length=10, choices=Status, default=Status.TRIAL)
    logo_key = models.CharField(max_length=255, blank=True)
    color_primary = models.CharField(max_length=7, default="#0E5A43", validators=[hex_color])
    color_accent = models.CharField(max_length=7, default="#F4B740", validators=[hex_color])
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return self.name


class TenantModel(TimestampedModel):
    """Base de toute donnée métier. Chaque table concrète doit être durcie par rls.harden_model
    dans une migration ; tests/test_isolation.py échoue si l'une d'elles l'oublie."""

    school = TenantForeignKey(
        "tenancy.School", on_delete=models.PROTECT, related_name="+", editable=False
    )

    class Meta:
        abstract = True


class Subscription(TenantModel):
    class Plan(models.TextChoices):
        ESSENTIAL = "ESSENTIAL", "Essentiel"
        COMPLETE = "COMPLETE", "Complet"
        PREMIUM = "PREMIUM", "Premium"

    plan = models.CharField(max_length=10, choices=Plan)
    starts_on = models.DateField()
    ends_on = models.DateField()
    student_quota = models.PositiveIntegerField(null=True, blank=True)
    annual_amount_xof = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gt=models.F("starts_on")),
                name="subscription_period_valid",
            )
        ]

    def __str__(self):
        return f"{self.plan} ({self.starts_on} - {self.ends_on})"


class SupportGrant(TenantModel):
    """Accès temporaire du support : demandé par la plateforme, approuvé par l'école."""

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Demandé"
        APPROVED = "APPROVED", "Approuvé"
        REFUSED = "REFUSED", "Refusé"
        REVOKED = "REVOKED", "Révoqué"

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status, default=Status.REQUESTED)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.status} : {self.reason[:40]}"
