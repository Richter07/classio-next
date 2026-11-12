import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from apps.tenancy.models import TenantModel, TimestampedModel

from .phone import normalize_phone


class UserManager(BaseUserManager):
    def _create(self, phone, password, **extra):
        user = self.model(phone=normalize_phone(phone), **extra)
        # None : mot de passe inutilisable jusqu'à l'activation par code d'accès.
        user.set_password(password)
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


class AccessCode(TimestampedModel):
    """Code d'activation remis par l'école, sur papier : il permet de choisir son mot de passe
    la première fois, ou d'en choisir un nouveau après un oubli.

    Pas de SMS : c'est l'école qui transmet l'accès. Le code n'est valable qu'avec le bon numéro,
    une seule fois, et seul son HMAC est stocké. En émettre un nouveau annule les précédents.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="access_codes")
    code_hmac = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    # Traçabilité : qui a émis le code, pour quelle école (pas de clé étrangère : la table est
    # globale et ne doit pas dépendre du contexte d'école).
    issued_by_user_id = models.UUIDField(null=True, blank=True)
    school_id = models.UUIDField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "used_at"], name="access_code_user_idx")]


class PushSubscription(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=128)
    auth = models.CharField(max_length=48)
