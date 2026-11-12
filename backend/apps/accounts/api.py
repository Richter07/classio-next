from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.students.models import Guardian
from apps.tenancy.context import tenant_context
from apps.tenancy.middleware import SESSION_SCHOOL_KEY, school_access
from apps.tenancy.models import School
from apps.tenancy.permissions import SessionAuth

from . import access
from .models import Membership
from .phone import InvalidPhone, normalize_phone

PARENT_SESSION_AGE = 60 * 60 * 24 * 30
STAFF_SESSION_AGE = 60 * 60 * 12
WRONG_CREDENTIALS = "Numéro ou mot de passe incorrect."


def client_ip(request) -> str:
    """Adresse réelle du client. Derrière N proxys de confiance, c'est la N-ième en partant de la
    fin de X-Forwarded-For : les valeurs plus à gauche peuvent être inventées par le client."""
    count = settings.TRUSTED_PROXY_COUNT
    forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
                 if p.strip()]
    if count and len(forwarded) >= count:
        return forwarded[-count]
    return request.META.get("REMOTE_ADDR", "")


def school_payload(school: School | None):
    if school is None:
        return None
    return {"id": str(school.pk), "name": school.name, "slug": school.slug,
            "color_primary": school.color_primary, "color_accent": school.color_accent}


def guardian_school_ids(user):
    with tenant_context(user_id=user.pk):
        return list(Guardian.objects.filter(user=user).values_list("school_id", flat=True))


class PublicView(APIView):
    authentication_classes = [SessionAuth]
    permission_classes = [AllowAny]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # DRF ne vérifie le CSRF que pour un utilisateur connecté : on l'exige aussi à la
        # connexion, pour empêcher un site tiers de connecter la victime à un autre compte.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            SessionAuth().enforce_csrf(request)


class CsrfView(PublicView):
    def get(self, request):
        get_token(request)
        return Response({"school": school_payload(request.school)})


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        try:
            return normalize_phone(super().to_internal_value(data))
        except InvalidPhone as exc:
            raise serializers.ValidationError("Ce numéro de téléphone n'est pas valide.") from exc


class ParentLoginSerializer(serializers.Serializer):
    phone = PhoneField(max_length=30)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


def _too_many():
    return Response({"detail": "Trop d'essais. Réessayez dans 15 minutes."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS)


class ParentLoginView(PublicView):
    def post(self, request):
        data = ParentLoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone, ip = data.validated_data["phone"], client_ip(request)
        if access.throttled("login", phone, ip, access.MAX_LOGIN_FAILURES_PER_PHONE,
                            access.MAX_LOGIN_FAILURES_PER_IP):
            return _too_many()
        user = authenticate(request, phone=phone, password=data.validated_data["password"])
        if user is None or not guardian_school_ids(user):
            access.record_failure("login", phone, ip)
            return Response({"detail": WRONG_CREDENTIALS}, status=400)
        access.clear_failures("login", phone)
        login(request, user)
        request.session.set_expiry(PARENT_SESSION_AGE)
        request.session.pop(SESSION_SCHOOL_KEY, None)
        return Response(me_payload(request, user))


class ActivateSerializer(serializers.Serializer):
    phone = PhoneField(max_length=30)
    code = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
    consent = serializers.BooleanField(default=False)


class ActivateView(PublicView):
    """Première connexion, ou mot de passe oublié : avec le code remis par l'école."""

    def post(self, request):
        data = ActivateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        phone, ip = v["phone"], client_ip(request)
        if access.throttled("activate", phone, ip, access.MAX_FAILURES_PER_PHONE,
                            access.MAX_FAILURES_PER_IP):
            return _too_many()

        # Le mot de passe est contrôlé avant de consommer le code : une erreur de saisie ne doit
        # pas obliger le parent à retourner à l'école.
        try:
            password_validation.validate_password(v["password"])
        except ValidationError as exc:
            return Response({"password": list(exc.messages)}, status=400)

        user = access.redeem_code(phone, v["code"])
        if user is None:
            access.record_failure("activate", phone, ip)
            return Response({"detail": "Code incorrect, déjà utilisé ou expiré. "
                                       "Demandez un nouveau code à l'école."}, status=400)
        schools = guardian_school_ids(user)
        if schools and not v["consent"]:
            # Le code n'est pas perdu pour autant : on annule la transaction de la requête.
            return Response({"consent": ["Confirmez avoir lu la politique de confidentialité."]},
                            status=400)

        user.set_password(v["password"])
        user.save(update_fields=["password"])
        access.clear_failures("activate", phone)
        now = timezone.now()
        for school_id in schools:
            with tenant_context(school_id, user.pk):
                Guardian.objects.filter(user=user).update(
                    activated_at=now, consent_at=now,
                    consent_version=settings.PRIVACY_VERSION)
        if schools:
            login(request, user)
            request.session.set_expiry(PARENT_SESSION_AGE)
            return Response({"kind": "parent", **me_payload(request, user)})
        return Response({"kind": "staff"})


class StaffLoginSerializer(ParentLoginSerializer):
    school = serializers.CharField(max_length=63, required=False, allow_blank=True)


class StaffLoginView(PublicView):
    def post(self, request):
        data = StaffLoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone, ip = data.validated_data["phone"], client_ip(request)
        if access.throttled("login", phone, ip, access.MAX_LOGIN_FAILURES_PER_PHONE,
                            access.MAX_LOGIN_FAILURES_PER_IP):
            return _too_many()

        user = authenticate(request, phone=phone, password=data.validated_data["password"])
        if user is None:
            access.record_failure("login", phone, ip)
            return Response({"detail": WRONG_CREDENTIALS}, status=400)

        school = request.school
        if school is None:
            with tenant_context(user_id=user.pk):
                school_ids = set(Membership.objects.filter(user=user, is_active=True)
                                 .values_list("school_id", flat=True))
            slug = (data.validated_data.get("school") or "").strip().lower()
            schools = School.objects.filter(pk__in=school_ids)
            if slug:
                schools = schools.filter(slug=slug)
            if schools.count() != 1:
                detail = ("Ce compte n'a pas accès à cette école." if slug or not school_ids
                          else "Indiquez le code de votre école.")
                return Response({"detail": detail, "need_school": bool(school_ids) and not slug},
                                status=400)
            school = schools.get()

        access_ = school_access(user, school)
        if not access_.memberships:
            return Response({"detail": "Ce compte n'a pas accès à cette école."}, status=400)
        if school.status == School.Status.SUSPENDED:
            return Response({"detail": "Espace suspendu."}, status=status.HTTP_403_FORBIDDEN)

        access.clear_failures("login", phone)
        login(request, user)
        request.session.set_expiry(STAFF_SESSION_AGE)
        request.session[SESSION_SCHOOL_KEY] = str(school.pk)
        request.school, request.memberships = school, access_.memberships
        request.roles = access_.roles
        return Response(me_payload(request, user))


class LogoutView(PublicView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeSerializer(serializers.Serializer):
    current = serializers.CharField(max_length=128, trim_whitespace=False)
    new = serializers.CharField(max_length=128, trim_whitespace=False)


class PasswordChangeView(APIView):
    authentication_classes = [SessionAuth]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = PasswordChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if not request.user.check_password(data.validated_data["current"]):
            return Response({"current": ["Mot de passe actuel incorrect."]}, status=400)
        try:
            password_validation.validate_password(data.validated_data["new"], request.user)
        except ValidationError as exc:
            return Response({"new": list(exc.messages)}, status=400)
        request.user.set_password(data.validated_data["new"])
        request.user.save(update_fields=["password"])
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, request.user)
        return Response({"changed": True})


def me_payload(request, user):
    memberships = request.memberships
    return {
        "phone": user.phone,
        "is_parent": bool(guardian_school_ids(user)),
        "school": school_payload(request.school) if memberships else None,
        "roles": sorted(request.roles),
        "full_name": memberships[0].full_name if memberships else "",
    }


class MeView(APIView):
    authentication_classes = [SessionAuth]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(me_payload(request, request.user))
