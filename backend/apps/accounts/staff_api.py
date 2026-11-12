"""Comptes du personnel, gérés par la direction de l'école."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.permissions import IsDirection, SessionAuth

from . import access
from .models import Membership, User
from .phone import InvalidPhone, normalize_phone

ROLE_CHOICES = [Membership.Role.TEACHER, Membership.Role.SECRETARY, Membership.Role.CENSOR,
                Membership.Role.DIRECTOR]


def staff_payload(m: Membership) -> dict:
    return {"id": str(m.pk), "full_name": m.full_name, "role": m.role,
            "role_label": m.get_role_display(), "phone": m.user.phone,
            "is_active": m.is_active, "activated": m.user.has_usable_password()}


def code_payload(code: str) -> dict:
    return {"code": access.display_code(code), "expires_at": access.code_expiry()}


class StaffView(APIView):
    authentication_classes = [SessionAuth]
    permission_classes = [IsDirection]


class StaffCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=30)
    role = serializers.ChoiceField(choices=ROLE_CHOICES)

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except InvalidPhone as exc:
            raise serializers.ValidationError("Numéro invalide.") from exc


class StaffListView(StaffView):
    def get(self, request):
        members = Membership.objects.select_related("user").order_by("-is_active", "full_name")
        return Response({"items": [staff_payload(m) for m in members]})

    def post(self, request):
        data = StaffCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = User.objects.filter(phone=v["phone"]).first() or User.objects.create_user(
            v["phone"])
        membership, created = Membership.objects.get_or_create(
            user=user, role=v["role"], defaults={"full_name": v["full_name"].strip()})
        if not created and membership.is_active:
            return Response({"phone": ["Cette personne a déjà ce rôle dans l'école."]},
                            status=400)
        membership.is_active = True
        membership.full_name = v["full_name"].strip()
        membership.save(update_fields=["is_active", "full_name", "updated_at"])
        body = staff_payload(membership)
        # Une personne qui a déjà un compte (autre école, parent d'élève) garde son mot de passe.
        if not user.has_usable_password():
            body["access"] = code_payload(
                access.issue_code(user, request.user.pk, request.school.pk))
        return Response(body, status=status.HTTP_201_CREATED)


class StaffAccessCodeView(StaffView):
    """Nouveau code d'accès : mot de passe oublié ou lettre perdue."""

    def post(self, request, pk):
        membership = get_object_or_404(Membership.objects.select_related("user"), pk=pk)
        code = access.issue_code(membership.user, request.user.pk, request.school.pk)
        return Response(code_payload(code))


class StaffActiveSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class StaffActiveView(StaffView):
    def post(self, request, pk):
        membership = get_object_or_404(Membership, pk=pk)
        data = StaffActiveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if membership.user_id == request.user.pk and not data.validated_data["is_active"]:
            return Response({"detail": "Vous ne pouvez pas désactiver votre propre compte."},
                            status=400)
        membership.is_active = data.validated_data["is_active"]
        membership.save(update_fields=["is_active", "updated_at"])
        return Response(staff_payload(membership))
