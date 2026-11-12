"""Configuration de l'école par sa direction : périodes, niveaux, classes, matières,
coefficients, attribution des enseignants, règles de calcul.

Tout passe par le contexte de l'école (RLS) : la direction ne touche que sa propre école.
Supprimer un élément déjà utilisé (une classe avec des élèves, une matière notée) est refusé.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Membership
from apps.tenancy.permissions import IsDirection, SessionAuth

from .models import (
    AcademicYear,
    Classroom,
    ClassSubject,
    Level,
    LevelSubject,
    Period,
    SchoolSettings,
    Subject,
)

IN_USE = "Impossible de supprimer : cet élément est déjà utilisé (élèves, notes ou évaluations)."


def num(value):
    return None if value is None else float(value)


def current_year() -> AcademicYear:
    year = AcademicYear.objects.filter(is_current=True).first()
    if year is None:
        today = date.today()
        start = today.year if today.month >= 8 else today.year - 1
        year = AcademicYear.objects.create(label=f"{start}-{start + 1}",
                                           starts_on=date(start, 9, 1),
                                           ends_on=date(start + 1, 7, 31), is_current=True)
    return year


def school_settings() -> SchoolSettings:
    return SchoolSettings.objects.first() or SchoolSettings.objects.create()


def snapshot() -> dict:
    year = current_year()
    settings = school_settings()
    levels = list(Level.objects.order_by("rank", "name"))
    return {
        "year": {"id": str(year.pk), "label": year.label, "starts_on": year.starts_on,
                 "ends_on": year.ends_on},
        "settings": {
            "max_score": num(settings.max_score), "decimals": settings.decimals,
            "rounding": settings.rounding, "average_formula": settings.average_formula,
            "appreciation_bands": settings.appreciation_bands,
            "formulas": [{"value": v, "label": label}
                         for v, label in SchoolSettings.Formula.choices],
        },
        "periods": [{"id": str(p.pk), "name": p.name, "rank": p.rank, "starts_on": p.starts_on,
                     "ends_on": p.ends_on, "is_closed": p.is_closed,
                     "assessments": p.assessments.count()}
                    for p in Period.objects.filter(year=year, level__isnull=True)
                    .order_by("rank")],
        "levels": [{"id": str(lv.pk), "name": lv.name, "rank": lv.rank,
                    "next_level": str(lv.next_level_id) if lv.next_level_id else None,
                    "subjects": [{"subject": str(ls.subject_id),
                                  "coefficient": num(ls.coefficient)}
                                 for ls in lv.subjects.all()]}
                   for lv in levels],
        "subjects": [{"id": str(s.pk), "name": s.name, "short_name": s.short_name}
                     for s in Subject.objects.order_by("name")],
        "classrooms": [{
            "id": str(c.pk), "name": c.name, "level": str(c.level_id),
            "students": c.enrollments.count(),
            "subjects": [{"id": str(cs.pk), "subject": str(cs.subject_id),
                          "teacher": str(cs.teacher_id) if cs.teacher_id else None,
                          "coefficient": num(cs.coefficient)}
                         for cs in c.subjects.all()],
        } for c in Classroom.objects.filter(year=year).prefetch_related("subjects")
            .order_by("level__rank", "name")],
        "teachers": [{"id": str(m.pk), "full_name": m.full_name}
                     for m in Membership.objects.filter(role=Membership.Role.TEACHER,
                                                        is_active=True).order_by("full_name")],
    }


class ConfigView(APIView):
    authentication_classes = [SessionAuth]
    permission_classes = [IsDirection]

    def done(self, code=status.HTTP_200_OK):
        return Response(snapshot(), status=code)

    def delete_or_refuse(self, obj):
        try:
            with transaction.atomic():
                obj.delete()
        except ProtectedError:
            return Response({"detail": IN_USE}, status=400)
        return self.done()

    def save_or_refuse(self, fn, duplicate="Ce nom existe déjà."):
        try:
            with transaction.atomic():
                fn()
        except IntegrityError:
            return Response({"detail": duplicate}, status=400)
        return self.done()


class ConfigSnapshotView(ConfigView):
    def get(self, request):
        return self.done()


# ------------------------------------------------------------------ Règles de calcul


class Band(serializers.Serializer):
    min = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal(0))
    label = serializers.CharField(max_length=40)


class SettingsSerializer(serializers.Serializer):
    max_score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal(1),
                                         max_value=Decimal(100), required=False)
    decimals = serializers.IntegerField(min_value=0, max_value=3, required=False)
    rounding = serializers.ChoiceField(choices=SchoolSettings.Rounding.choices, required=False)
    average_formula = serializers.ChoiceField(choices=SchoolSettings.Formula.choices,
                                              required=False)
    appreciation_bands = Band(many=True, required=False, max_length=12)


class SettingsView(ConfigView):
    def patch(self, request):
        data = SettingsSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        settings = school_settings()
        for key, value in data.validated_data.items():
            if key == "appreciation_bands":
                value = [{"min": float(b["min"]), "label": b["label"].strip()} for b in value]
            setattr(settings, key, value)
        settings.save()
        return self.done()


# ------------------------------------------------------------------ Périodes

PRESETS = {
    "TRIMESTER": [("Trimestre 1", (9, 1), (12, 20)), ("Trimestre 2", (1, 5), (3, 31)),
                  ("Trimestre 3", (4, 10), (7, 15))],
    "SEMESTER": [("Semestre 1", (9, 1), (1, 31)), ("Semestre 2", (2, 1), (7, 15))],
}


class PresetSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=list(PRESETS))


class PeriodPresetView(ConfigView):
    def post(self, request):
        data = PresetSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        year = current_year()
        if Period.objects.filter(year=year).exists():
            return Response({"detail": "Les périodes de l'année existent déjà."}, status=400)
        first = year.starts_on.year
        for rank, (name, (sm, sd), (em, ed)) in enumerate(PRESETS[data.validated_data["kind"]], 1):
            Period.objects.create(
                year=year, name=name, rank=rank,
                starts_on=date(first + (sm < 8), sm, sd), ends_on=date(first + (em < 8), em, ed))
        return self.done(status.HTTP_201_CREATED)


class PeriodSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40, required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False)
    is_closed = serializers.BooleanField(required=False)


class PeriodView(ConfigView):
    def patch(self, request, pk):
        period = get_object_or_404(Period, pk=pk)
        data = PeriodSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        for key, value in data.validated_data.items():
            setattr(period, key, value)
        if period.ends_on <= period.starts_on:
            return Response({"detail": "La fin doit suivre le début."}, status=400)
        period.save()
        return self.done()

    def delete(self, request, pk):
        return self.delete_or_refuse(get_object_or_404(Period, pk=pk))


# ------------------------------------------------------------------ Niveaux et classes


class LevelSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    next_level = serializers.UUIDField(required=False, allow_null=True)


class LevelsView(ConfigView):
    def post(self, request):
        data = LevelSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rank = (Level.objects.order_by("-rank").values_list("rank", flat=True).first() or 0) + 1
        return self.save_or_refuse(lambda: Level.objects.create(
            name=data.validated_data["name"].strip(), rank=rank), "Ce niveau existe déjà.")


class LevelView(ConfigView):
    def patch(self, request, pk):
        level = get_object_or_404(Level, pk=pk)
        data = LevelSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        if "name" in data.validated_data:
            level.name = data.validated_data["name"].strip()
        if "next_level" in data.validated_data:
            level.next_level = (get_object_or_404(Level, pk=data.validated_data["next_level"])
                                if data.validated_data["next_level"] else None)
        return self.save_or_refuse(level.save, "Ce niveau existe déjà.")

    def delete(self, request, pk):
        return self.delete_or_refuse(get_object_or_404(Level, pk=pk))


class ClassroomSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    level = serializers.UUIDField()


def ensure_class_subjects(classroom):
    """Une classe enseigne toutes les matières de son niveau."""
    existing = set(classroom.subjects.values_list("subject_id", flat=True))
    for link in LevelSubject.objects.filter(level_id=classroom.level_id):
        if link.subject_id not in existing:
            ClassSubject.objects.create(classroom=classroom, subject_id=link.subject_id)


class ClassroomsView(ConfigView):
    def post(self, request):
        data = ClassroomSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        level = get_object_or_404(Level, pk=data.validated_data["level"])

        def create():
            classroom = Classroom.objects.create(year=current_year(), level=level,
                                                 name=data.validated_data["name"].strip())
            ensure_class_subjects(classroom)

        return self.save_or_refuse(create, "Cette classe existe déjà.")


class ClassroomView(ConfigView):
    def patch(self, request, pk):
        classroom = get_object_or_404(Classroom, pk=pk)
        data = ClassroomSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        if "name" in data.validated_data:
            classroom.name = data.validated_data["name"].strip()
        return self.save_or_refuse(classroom.save, "Cette classe existe déjà.")

    def delete(self, request, pk):
        classroom = get_object_or_404(Classroom, pk=pk)
        if classroom.enrollments.exists():
            return Response({"detail": IN_USE}, status=400)
        return self.delete_or_refuse(classroom)


# ------------------------------------------------------------------ Matières et coefficients


class SubjectSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    short_name = serializers.CharField(max_length=12, required=False, allow_blank=True)


class SubjectsView(ConfigView):
    def post(self, request):
        data = SubjectSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self.save_or_refuse(lambda: Subject.objects.create(
            name=data.validated_data["name"].strip(),
            short_name=data.validated_data.get("short_name", "")), "Cette matière existe déjà.")


class SubjectView(ConfigView):
    def patch(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        data = SubjectSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        for key, value in data.validated_data.items():
            setattr(subject, key, value.strip())
        return self.save_or_refuse(subject.save, "Cette matière existe déjà.")

    def delete(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        if ClassSubject.objects.filter(subject=subject, assessments__isnull=False).exists():
            return Response({"detail": IN_USE}, status=400)
        with transaction.atomic():
            ClassSubject.objects.filter(subject=subject).delete()
            LevelSubject.objects.filter(subject=subject).delete()
        return self.delete_or_refuse(subject)


class CoefficientSerializer(serializers.Serializer):
    # null : la matière n'est pas enseignée à ce niveau.
    coefficient = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True,
                                           min_value=Decimal("0.01"), max_value=Decimal(20))


class LevelSubjectView(ConfigView):
    """Coefficient d'une matière pour un niveau. Ajouter la matière l'ouvre dans toutes les
    classes du niveau ; la retirer n'est possible que si elle n'a pas encore été notée."""

    def put(self, request, level_id, subject_id):
        level = get_object_or_404(Level, pk=level_id)
        subject = get_object_or_404(Subject, pk=subject_id)
        data = CoefficientSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        coefficient = data.validated_data["coefficient"]
        classes = Classroom.objects.filter(level=level, year=current_year())
        if coefficient is None:
            taught = ClassSubject.objects.filter(classroom__in=classes, subject=subject)
            if taught.filter(assessments__isnull=False).exists():
                return Response({"detail": "Cette matière a déjà des évaluations à ce niveau."},
                                status=400)
            with transaction.atomic():
                taught.delete()
                LevelSubject.objects.filter(level=level, subject=subject).delete()
            return self.done()
        with transaction.atomic():
            LevelSubject.objects.update_or_create(level=level, subject=subject,
                                                  defaults={"coefficient": coefficient})
            for classroom in classes:
                ensure_class_subjects(classroom)
        return self.done()


class ClassSubjectSerializer(serializers.Serializer):
    teacher = serializers.UUIDField(required=False, allow_null=True)
    # Vide : reprend le coefficient du niveau.
    coefficient = serializers.DecimalField(max_digits=4, decimal_places=2, required=False,
                                           allow_null=True, min_value=Decimal("0.01"),
                                           max_value=Decimal(20))


class ClassSubjectView(ConfigView):
    def patch(self, request, pk):
        cs = get_object_or_404(ClassSubject, pk=pk)
        data = ClassSubjectSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        if "teacher" in data.validated_data:
            teacher_id = data.validated_data["teacher"]
            cs.teacher = (get_object_or_404(Membership, pk=teacher_id,
                                            role=Membership.Role.TEACHER)
                          if teacher_id else None)
        if "coefficient" in data.validated_data:
            cs.coefficient = data.validated_data["coefficient"]
        cs.save()
        return self.done()
