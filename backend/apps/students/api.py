from datetime import date

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicYear, Classroom
from apps.accounts import access
from apps.accounts.phone import InvalidPhone, normalize_phone
from apps.tenancy.permissions import IsOffice, SessionAuth

from . import importer
from .models import Enrollment, Guardian, ImportBatch, Student


class OfficeView(APIView):
    authentication_classes = [SessionAuth]
    permission_classes = [IsOffice]


def code_payload(code: str) -> dict:
    return {"code": access.display_code(code), "expires_at": access.code_expiry()}


class ClassroomsView(OfficeView):
    def get(self, request):
        year = AcademicYear.objects.filter(is_current=True).first()
        return Response({"items": [
            {"id": str(c.pk), "name": c.name}
            for c in Classroom.objects.filter(year=year).order_by("name")]})


class StudentCreateSerializer(serializers.Serializer):
    matricule = serializers.CharField(max_length=40)
    last_name = serializers.CharField(max_length=80)
    first_name = serializers.CharField(max_length=120)
    birth_date = serializers.DateField()
    sex = serializers.ChoiceField(choices=["F", "M", ""], required=False, allow_blank=True)
    classroom = serializers.UUIDField()
    guardian_name = serializers.CharField(max_length=160)
    guardian_phone = serializers.CharField(max_length=30)

    def validate_guardian_phone(self, value):
        try:
            return normalize_phone(value)
        except InvalidPhone as exc:
            raise serializers.ValidationError("Numéro invalide.") from exc

    def validate_matricule(self, value):
        if Student.objects.filter(matricule=value.strip()).exists():
            raise serializers.ValidationError("Ce matricule existe déjà.")
        return value.strip()

    def validate_birth_date(self, value):
        if not 1990 <= value.year <= date.today().year - 2:
            raise serializers.ValidationError("Date improbable.")
        return value


class StudentsView(OfficeView):
    def get(self, request):
        year = AcademicYear.objects.filter(is_current=True).first()
        enrollments = Enrollment.objects.filter(year=year).select_related(
            "student", "classroom").order_by("classroom__name", "student__last_name",
                                             "student__first_name")
        if classroom := request.query_params.get("classroom"):
            enrollments = enrollments.filter(classroom_id=classroom)
        if q := request.query_params.get("q", "").strip():
            enrollments = enrollments.filter(
                Q(student__last_name__icontains=q) | Q(student__first_name__icontains=q)
                | Q(student__matricule__icontains=q))
        enrollments = list(enrollments[:500])
        guardians = {}
        for link in Guardian.students.through.objects.filter(
                student_id__in=[e.student_id for e in enrollments]).select_related("guardian"):
            g = link.guardian
            guardians.setdefault(link.student_id, []).append({
                "id": str(g.pk), "name": g.full_name, "phone": g.phone,
                "activated": g.activated_at is not None})
        return Response({"items": [{
            "id": str(e.student_id), "matricule": e.student.matricule,
            "name": f"{e.student.last_name} {e.student.first_name}",
            "birth_date": e.student.birth_date, "sex": e.student.sex,
            "classroom": e.classroom.name, "guardians": guardians.get(e.student_id, []),
        } for e in enrollments]})

    def post(self, request):
        data = StudentCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        classroom = get_object_or_404(Classroom.objects.filter(year__is_current=True),
                                      pk=v["classroom"])
        student = Student.objects.create(
            matricule=v["matricule"], last_name=v["last_name"].strip().upper(),
            first_name=v["first_name"].strip(), birth_date=v["birth_date"],
            sex=v.get("sex", ""))
        Enrollment.objects.create(student=student, classroom=classroom, year=classroom.year)
        guardian, is_new = importer.link_guardian(student, v["guardian_phone"],
                                                  v["guardian_name"].strip())
        return Response({"id": str(student.pk), "guardian_id": str(guardian.pk),
                         "guardian_created": is_new,
                         "guardian_activated": guardian.user.has_usable_password()},
                        status=status.HTTP_201_CREATED)


class GuardianAccessCodeView(OfficeView):
    """Code d'accès d'un parent, à lui donner de vive voix ou sur papier (oubli, lettre perdue)."""

    def post(self, request, pk):
        guardian = get_object_or_404(Guardian.objects.select_related("user"), pk=pk)
        code = access.issue_code(guardian.user, request.user.pk, request.school.pk)
        return Response(code_payload(code))


class LettersSerializer(serializers.Serializer):
    classroom = serializers.UUIDField(required=False)
    guardians = serializers.ListField(child=serializers.UUIDField(), required=False,
                                      max_length=500)
    # Par défaut, seuls les parents qui n'ont pas encore activé leur compte reçoivent un code :
    # en réémettre un annulerait sans raison la lettre que les autres ont peut-être encore.
    include_activated = serializers.BooleanField(default=False)


class AccessLettersView(OfficeView):
    def post(self, request):
        data = LettersSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        guardians = Guardian.objects.select_related("user")
        if v.get("classroom"):
            guardians = guardians.filter(
                students__enrollments__classroom_id=v["classroom"],
                students__enrollments__year__is_current=True)
        elif v.get("guardians"):
            guardians = guardians.filter(pk__in=v["guardians"])
        else:
            return Response({"detail": "Choisissez une classe ou des parents."}, status=400)
        if not v["include_activated"]:
            guardians = [g for g in guardians.distinct() if not g.user.has_usable_password()]
        ids = [str(g.pk) for g in guardians]
        if not ids:
            return Response({"detail": "Tous ces parents ont déjà activé leur compte."},
                            status=400)
        from apps.documents import jobs
        from apps.documents.tasks import access_letters

        job_id = jobs.start(access_letters, user_id=request.user.pk, school_id=request.school.pk,
                            filename="lettres-acces-classio.pdf", guardian_ids=ids,
                            reissue_activated=v["include_activated"])
        return Response({"job": job_id, "count": len(ids)}, status=status.HTTP_202_ACCEPTED)


class TemplateView(OfficeView):
    def get(self, request):
        response = HttpResponse(
            importer.template_workbook(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="modele-import-eleves.xlsx"'
        return response


class ImportCheckView(OfficeView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Aucun fichier reçu."}, status=400)
        try:
            report = importer.check(upload.name, upload.read(importer.MAX_BYTES + 1))
        except importer.ImportFileError as exc:
            return Response({"detail": str(exc)}, status=400)
        membership = next((m for m in request.memberships
                           if m.role in ("SECRETARY", "DIRECTOR")), None)
        batch = ImportBatch.objects.create(
            kind=ImportBatch.Kind.STUDENTS, status=ImportBatch.Status.CHECKED,
            file_key="", report=report, created_by=membership)
        return Response({"id": str(batch.pk), **report})


class ImportApplyView(OfficeView):
    def post(self, request, pk):
        batch = get_object_or_404(ImportBatch, pk=pk, kind=ImportBatch.Kind.STUDENTS)
        if batch.status != ImportBatch.Status.CHECKED:
            return Response({"detail": "Cet import a déjà été traité."}, status=400)
        try:
            result = importer.apply(batch.report)
        except Exception as exc:  # une donnée a changé depuis le contrôle
            return Response({"detail": f"Import interrompu, rien n'a été créé : {exc}"},
                            status=400)
        new_guardians = [str(g.pk) for g in result.pop("new_guardians")]
        batch.status = ImportBatch.Status.APPLIED
        # Le rapport contenait les données des élèves : on ne garde que les compteurs.
        batch.report = {k: v for k, v in batch.report.items() if k != "rows"} | result
        batch.save(update_fields=["status", "report", "updated_at"])
        return Response({**result, "new_guardian_ids": new_guardians})
