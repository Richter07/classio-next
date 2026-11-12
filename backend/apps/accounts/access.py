"""Accès sans SMS : codes d'activation remis par l'école, puis mot de passe choisi par la personne.

Protections :
- code de 8 caractères dans un alphabet sans ambiguïté (pas de 0/O, 1/I/L) : environ 40 bits ;
- valable seulement avec le numéro de téléphone associé, une seule fois, 30 jours ;
- 5 essais ratés par numéro et 30 par adresse IP sur 15 minutes ;
- seul le HMAC est stocké, avec une clé distincte de DJANGO_SECRET_KEY.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import AccessCode, User

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LENGTH = 8
VALIDITY = timedelta(days=30)
WINDOW = 15 * 60
MAX_FAILURES_PER_PHONE = 5
MAX_FAILURES_PER_IP = 30
MAX_LOGIN_FAILURES_PER_PHONE = 5
MAX_LOGIN_FAILURES_PER_IP = 50


def normalize_code(raw: str) -> str:
    return "".join(c for c in str(raw).upper() if c.isalnum())


def display_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


def _hmac(user_id, code: str) -> str:
    key = settings.ACCESS_CODE_KEY.encode()
    return hmac.new(key, f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_code(user: User, issued_by_user_id=None, school_id=None, code: str | None = None) -> str:
    """Crée un code et annule les précédents non utilisés. Renvoie le code en clair, une fois."""
    code = normalize_code(code) if code else "".join(
        secrets.choice(ALPHABET) for _ in range(LENGTH))
    now = timezone.now()
    AccessCode.objects.filter(user=user, used_at__isnull=True).update(expires_at=now)
    AccessCode.objects.create(
        user=user, code_hmac=_hmac(user.pk, code), expires_at=now + VALIDITY,
        issued_by_user_id=issued_by_user_id, school_id=school_id)
    return code


def code_expiry() -> timezone.datetime:
    return timezone.now() + VALIDITY


def throttled(kind: str, phone: str, ip: str, per_phone: int, per_ip: int) -> bool:
    return (cache.get(f"{kind}:fail:phone:{phone}") or 0) >= per_phone or (
        cache.get(f"{kind}:fail:ip:{ip}") or 0) >= per_ip


def record_failure(kind: str, phone: str, ip: str) -> None:
    # Dans Redis et non en base : un échec annule la transaction de la requête.
    for key in (f"{kind}:fail:phone:{phone}", f"{kind}:fail:ip:{ip}"):
        cache.add(key, 0, WINDOW)
        cache.incr(key)


def clear_failures(kind: str, phone: str) -> None:
    cache.delete(f"{kind}:fail:phone:{phone}")


def redeem_code(phone: str, raw_code: str) -> User | None:
    """Vérifie le code ; s'il est bon, le consomme et renvoie l'utilisateur."""
    user = User.objects.filter(phone=phone, is_active=True).first()
    code = normalize_code(raw_code)
    if user is None or len(code) != LENGTH:
        return None
    expected = _hmac(user.pk, code)
    candidate = AccessCode.objects.filter(
        user=user, used_at__isnull=True, expires_at__gt=timezone.now()).order_by(
        "-created_at").first()
    if candidate is None or not hmac.compare_digest(candidate.code_hmac, expected):
        return None
    candidate.used_at = timezone.now()
    candidate.save(update_fields=["used_at"])
    return user
