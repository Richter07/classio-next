import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from apps.tenancy.models import TenantModel, TimestampedModel

from .phone import normalize_phone


class UserManager(BaseUserManager):
    def _create(self, phone, password, **extra):
        user = self.model(phone=normalize_phone(phone), **extra)
        user.set_password(password)  # None donne un mot de passe inutilisable : parents, OTP.
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra):
        return self._create(phone, password, **extra)

    def create_superuser(self, phone, password=None, **extra):
        return self._create(phone, password, is_staff=True, is_superuser=True, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Identité globale : un numéro, un compte, même sur plusieurs écoles.

    Enseignants vacataires et parents interviennent souvent dans plusieurs établissements.
    Cette table n'est pas isolée par école, elle ne porte donc aucun nom : l'identité affichée
    vit dans Membership et Guardian, qui sont propres à chaque école.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True, help_text="Format E.164.")
    email = models.EmailField(null=True, blank=True, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Accès à l'administration Django.")
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()
    USERNAME_FIELD = "phone"

    def __str__(self):
        return self.phone


class Membership(TenantModel):
    """Rôle du personnel dans une école. Le parent n'y figure pas : voir students.Guardian.
    Le super-admin non plus : il n'est rattaché à aucune école."""

    class Role(models.TextChoices):
        DIRECTOR = "DIRECTOR", "Directeur / Administrateur"
        CENSOR = "CENSOR", "Censeur"
        SECRETARY = "SECRETARY", "Secrétariat"
        TEACHER = "TEACHER", "Enseignant"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role)
    full_name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "user", "role"], name="membership_unique_role"
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.role})"


class OtpChallenge(TimestampedModel):
    """Code à usage unique. Globale : elle précède l'authentification et ne dit rien de l'école.
    Seul le HMAC du code est stocké : un SHA-256 simple de 6 chiffres se casse en un instant."""

    phone = models.CharField(max_length=20, db_index=True)
    code_hmac = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)


class PushSubscription(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=128)
    auth = models.CharField(max_length=48)
