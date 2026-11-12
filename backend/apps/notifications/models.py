from django.db import models

from apps.tenancy.models import TenantModel


class Notification(TenantModel):
    class Kind(models.TextChoices):
        ACTIVATION = "ACTIVATION", "Activation du compte"
        NEW_GRADE = "NEW_GRADE", "Nouvelle note"
        REPORT_CARD = "REPORT_CARD", "Bulletin disponible"
        CORRECTION = "CORRECTION", "Correction de note"
        ANNOUNCEMENT = "ANNOUNCEMENT", "Annonce"

    class Channel(models.TextChoices):
        IN_APP = "IN_APP", "Dans l'application"
        PUSH = "PUSH", "Notification push"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        SMS = "SMS", "SMS"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "En file"
        SENT = "SENT", "Envoyée"
        DELIVERED = "DELIVERED", "Distribuée"
        READ = "READ", "Lue"
        FAILED = "FAILED", "Échec"

    guardian = models.ForeignKey(
        "students.Guardian", on_delete=models.CASCADE, related_name="notifications"
    )
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    kind = models.CharField(max_length=12, choices=Kind)
    channel = models.CharField(max_length=8, choices=Channel)
    status = models.CharField(max_length=9, choices=Status, default=Status.QUEUED)
    message = models.CharField(max_length=255, blank=True)
    # Chemin de l'application vers lequel la notification mène (ex. la fiche de l'enfant).
    link = models.CharField(max_length=255, blank=True)
    provider_ref = models.CharField(max_length=120, blank=True)
    cost_xof = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    error = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["school", "status"], name="notification_status_idx")]
