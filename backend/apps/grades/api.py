from decimal import Decimal, InvalidOperation

from django.db import connection
from django.db.models import Avg, Count, Max, Min, Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicYear, Classroom, ClassSubject, Period
from apps.notifications.models import Notification
from apps.notifications.services import notify_guardians_of
from apps.students.models import Enrollment, Guardian
from apps.tenancy.permissions import (
    IsDirection,
    IsTeacher,
    SessionAuth,
    is_direction,
    teacher_membership_ids,
)

from . import release as releases
from .bulletin import KIND_LABELS, build_pages, ordinal, render_pdf
from .calculations import compute_class_results
from .models import Assessment, Grade, GradeAudit

S = Grade.Status
STATUS_LABELS = dict(S.choices)


class StaffView(APIView):
    authentication_classes = [SessionAuth]


def num(value):
    return None if value is None else float(value)


def current_year():
    return AcademicYear.objects.filter(is_current=True).first()


def active_enrollments(classroom):
    return (
        Enrollment.objects.filter(classroom=classroom)
        .exclude(status=Enrollment.Status.LEFT)
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
    )


def periods_of(classroom):
    return Period.objects.filter(year_id=classroom.year_id).filter(
        Q(level__isnull=True) | Q(level_id=classroom.level_id)).order_by("rank")


def annotate_assessments(qs):
    """Tout ce qu'il faut pour résumer une évaluation, en une seule requête pour toute la liste."""
    grades_filled = Q(grades__value__isnull=False) | Q(grades__is_absent=True)
    return qs.annotate(
        n_total=Count("grades"),
        n_draft=Count("grades", filter=Q(grades__status=S.DRAFT)),
        n_submitted=Count("grades", filter=Q(grades__status=S.SUBMITTED)),
        n_validated=Count("grades", filter=Q(grades__status=S.VALIDATED)),
        n_filled=Count("grades", filter=grades_filled),
        avg_value=Avg("grades__value"), min_value=Min("grades__value"),
        max_value=Max("grades__value"),
    )


def state_of(a) -> str:
    """Un seul statut lisible pour toute une évaluation."""
    if not a.n_total or a.n_draft:
        return S.DRAFT
    if a.n_submitted:
        return S.SUBMITTED
    if a.n_validated:
        return S.VALIDATED
    return S.PUBLISHED


def enrolled_counts(classroom_ids) -> dict:
    return dict(
        Enrollment.objects.filter(classroom_id__in=classroom_ids)
        .exclude(status=Enrollment.Status.LEFT)
        .values_list("classroom_id").annotate(n=Count("id")).values_list("classroom_id", "n"))


def assessment_summary(assessment, enrolled_count=None):
    if not hasattr(assessment, "n_total"):
        assessment = annotate_assessments(
            Assessment.objects.filter(pk=assessment.pk).select_related("period")).get()
    state = state_of(assessment)
    return {
        "id": str(assessment.pk),
        "kind": assessment.kind, "kind_label": KIND_LABELS[assessment.kind],
        "title": assessment.title, "held_on": assessment.held_on,
        "max_score": num(assessment.max_score), "weight": num(assessment.weight),
        "period_id": str(assessment.period_id), "period": assessment.period.name,
        "period_closed": assessment.period.is_closed,
        "state": state, "state_label": STATUS_LABELS[state],
        "filled": assessment.n_filled, "enrolled": enrolled_count,
        "average": num(assessment.avg_value), "lowest": num(assessment.min_value),
        "highest": num(assessment.max_value),
    }


def accessible_assessment(request, pk) -> Assessment:
    assessment = get_object_or_404(
        Assessment.objects.select_related(
            "class_subject__classroom", "class_subject__subject", "class_subject__teacher",
            "period"),
        pk=pk,
    )
    if not is_direction(request) and (
        assessment.class_subject.teacher_id not in teacher_membership_ids(request)
    ):
        raise Http404
    return assessment


# ---------------------------------------------------------------- Enseignant


class TeacherClassSubjectsView(StaffView):
    permission_classes = [IsTeacher]

    def get(self, request):
        year = current_year()
        assessments = annotate_assessments(Assessment.objects.select_related("period")).order_by(
            "period__rank", "held_on", "created_at")
        qs = ClassSubject.objects.filter(classroom__year=year).select_related(
            "classroom", "subject", "teacher").prefetch_related(
            Prefetch("assessments", queryset=assessments))
        if not is_direction(request):
            qs = qs.filter(teacher_id__in=teacher_membership_ids(request))
        qs = list(qs.order_by("classroom__name", "subject__name"))
        enrolled = enrolled_counts({cs.classroom_id for cs in qs})
        periods = {}
        items = []
        for cs in qs:
            if cs.classroom_id not in periods:
                periods[cs.classroom_id] = [{"id": str(p.pk), "name": p.name,
                                             "closed": p.is_closed}
                                            for p in periods_of(cs.classroom)]
            count = enrolled.get(cs.classroom_id, 0)
            items.append({
                "id": str(cs.pk),
                "classroom": {"id": str(cs.classroom_id), "name": cs.classroom.name},
                "subject": cs.subject.name,
                "teacher": cs.teacher.full_name if cs.teacher else "",
                "enrolled": count,
                "periods": periods[cs.classroom_id],
                "assessments": [assessment_summary(a, count) for a in cs.assessments.all()],
            })
        return Response({"year": year.label if year else None, "class_subjects": items})


class AssessmentCreateSerializer(serializers.Serializer):
    period = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=Assessment.Kind.choices)
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    held_on = serializers.DateField(required=False, allow_null=True)
    max_score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal(1),
                                         max_value=Decimal(100), default=Decimal(20))


class AssessmentCreateView(StaffView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        cs = get_object_or_404(ClassSubject.objects.select_related("classroom"), pk=pk)
        if not is_direction(request) and cs.teacher_id not in teacher_membership_ids(request):
            raise Http404
        data = AssessmentCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        period = get_object_or_404(periods_of(cs.classroom), pk=data.validated_data["period"])
        if period.is_closed:
            return Response({"detail": "Cette période est close."}, status=400)
        assessment = Assessment.objects.create(
            class_subject=cs, period=period, kind=data.validated_data["kind"],
            title=data.validated_data.get("title", ""),
            held_on=data.validated_data.get("held_on"),
            max_score=data.validated_data["max_score"],
        )
        return Response({"id": str(assessment.pk)}, status=status.HTTP_201_CREATED)


class GridView(StaffView):
    permission_classes = [IsTeacher]

    def get(self, request, pk):
        assessment = accessible_assessment(request, pk)
        enrollments = list(active_enrollments(assessment.class_subject.classroom))
        grades = {g.student_id: g for g in assessment.grades.all()}
        owner = assessment.class_subject.teacher_id in teacher_membership_ids(request)
        rows = []
        for e in enrollments:
            g = grades.get(e.student_id)
            rows.append({
                "student_id": str(e.student_id),
                "name": f"{e.student.last_name} {e.student.first_name}",
                "matricule": e.student.matricule,
                "grade_id": str(g.pk) if g else None,
                "value": num(g.value) if g else None,
                "is_absent": g.is_absent if g else False,
                "status": g.status if g else S.DRAFT,
                "revision": g.revision if g else 0,
            })
        summary = assessment_summary(assessment, len(enrollments))
        return Response({
            "assessment": summary,
            "classroom": assessment.class_subject.classroom.name,
            "subject": assessment.class_subject.subject.name,
            "teacher": assessment.class_subject.teacher.full_name
            if assessment.class_subject.teacher else "",
            "can_edit": owner and summary["state"] == S.DRAFT and not assessment.period.is_closed,
            "can_review": is_direction(request),
            "rows": rows,
        })


class GradeItemSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    value = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    is_absent = serializers.BooleanField(default=False)
    mutation_id = serializers.UUIDField()
    base_revision = serializers.IntegerField(allow_null=True, required=False)


class GradeBatchSerializer(serializers.Serializer):
    items = GradeItemSerializer(many=True, max_length=300)


def parse_value(raw, max_score):
    if raw in (None, ""):
        return None, None
    try:
        value = Decimal(str(raw).replace(",", ".").strip())
    except InvalidOperation:
        return None, "Note illisible."
    if value < 0 or value > max_score:
        return None, f"La note doit être entre 0 et {max_score:g}."
    if value != value.quantize(Decimal("0.01")):
        return None, "Deux décimales au plus."
    return value, None


class GradeBatchView(StaffView):
    """Enregistrement idempotent des cellules, conçu pour la file hors ligne du téléphone."""

    permission_classes = [IsTeacher]

    def post(self, request, pk):
        assessment = accessible_assessment(request, pk)
        mine = teacher_membership_ids(request)
        if assessment.class_subject.teacher_id not in mine:
            return Response({"detail": "Seul l'enseignant de la matière saisit ces notes."},
                            status=403)
        if assessment.period.is_closed:
            return Response({"detail": "Cette période est close : les notes ne se modifient "
                                       "plus."}, status=400)
        data = GradeBatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        enrolled = set(
            active_enrollments(assessment.class_subject.classroom)
            .values_list("student_id", flat=True))
        existing = {g.student_id: g for g in assessment.grades.all()}
        results = []
        for item in data.validated_data["items"]:
            student_id = item["student"]
            out = {"student": str(student_id), "mutation_id": str(item["mutation_id"])}
            grade = existing.get(student_id)
            if grade and grade.client_mutation_id == item["mutation_id"]:
                results.append({**out, "status": "ok", **self.state(grade)})
                continue
            if student_id not in enrolled:
                results.append({**out, "status": "error", "message": "Élève hors de la classe."})
                continue
            value, error = parse_value(item.get("value"), assessment.max_score)
            if error:
                results.append({**out, "status": "error", "message": error})
                continue
            absent = item["is_absent"]
            if absent:
                value = None
            if grade is None:
                grade = Grade.objects.create(
                    assessment=assessment, student_id=student_id, value=value,
                    is_absent=absent, client_mutation_id=item["mutation_id"],
                    entered_by_id=mine[0],
                )
                existing[student_id] = grade
            elif grade.status != S.DRAFT:
                results.append({**out, "status": "locked", **self.state(grade),
                                "message": "Note déjà envoyée à la direction."})
                continue
            elif item.get("base_revision") not in (None, grade.revision):
                results.append({**out, "status": "conflict", **self.state(grade),
                                "message": "Cette note a été modifiée ailleurs."})
                continue
            else:
                grade.value, grade.is_absent = value, absent
                grade.client_mutation_id = item["mutation_id"]
                grade.revision += 1
                grade.save(update_fields=["value", "is_absent", "client_mutation_id",
                                          "revision", "updated_at"])
            results.append({**out, "status": "ok", **self.state(grade)})
        return Response({"results": results})

    @staticmethod
    def state(grade):
        return {"value": num(grade.value), "is_absent": grade.is_absent,
                "revision": grade.revision, "grade_status": grade.status}


class SubmitView(StaffView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        assessment = accessible_assessment(request, pk)
        if assessment.class_subject.teacher_id not in teacher_membership_ids(request):
            raise Http404
        if assessment.period.is_closed:
            return Response({"detail": "Cette période est close."}, status=400)
        enrolled = set(active_enrollments(assessment.class_subject.classroom)
                       .values_list("student_id", flat=True))
        complete = set(assessment.grades.filter(Q(value__isnull=False) | Q(is_absent=True))
                       .values_list("student_id", flat=True))
        missing = len(enrolled - complete)
        if missing:
            return Response({"detail": f"{missing} élève(s) sans note ni absence.",
                             "missing": missing}, status=400)
        changed = assessment.grades.filter(status=S.DRAFT).update(
            status=S.SUBMITTED, updated_at=timezone.now())
        return Response({"submitted": changed})


# ---------------------------------------------------------------- Direction


def _set_reason(reason: str):
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.change_reason', %s, true)", [reason[:255]])


def publish_assessments(assessments) -> int:
    """Publie et prévient les familles. Renvoie le nombre de notes publiées."""
    now = timezone.now()
    total = 0
    for assessment in assessments:
        grades = assessment.grades.filter(status__in=[S.SUBMITTED, S.VALIDATED]).select_related(
            "student")
        students = {g.student_id: g.student for g in grades}
        values = {g.student_id: g for g in grades}
        total += grades.update(status=S.PUBLISHED, published_at=now, updated_at=now)
        subject = assessment.class_subject.subject.name
        school_id = assessment.school_id

        def message(student, values=values, subject=subject, assessment=assessment,
                    school_id=school_id):
            grade = values[student.pk]
            mark = "absent(e)" if grade.is_absent else f"{grade.value:g}/{assessment.max_score:g}"
            label = KIND_LABELS[assessment.kind].lower()
            return (f"Nouvelle note pour {student.first_name} : {mark} en {subject} "
                    f"({label}).", f"/parent/enfant/{school_id}/{student.pk}")

        notify_guardians_of(students, Notification.Kind.NEW_GRADE, message)
    return total


class DirectionOverviewView(StaffView):
    permission_classes = [IsDirection]

    def get(self, request):
        year = current_year()
        grades = Grade.objects.filter(assessment__class_subject__classroom__year=year)
        guardians = Guardian.objects.all()
        return Response({
            "year": year.label if year else None,
            "students": Enrollment.objects.filter(year=year).exclude(
                status=Enrollment.Status.LEFT).count(),
            "classrooms": Classroom.objects.filter(year=year).count(),
            "to_validate": Assessment.objects.filter(
                grades__status=S.SUBMITTED, period__year=year).distinct().count(),
            "to_publish": Assessment.objects.filter(
                grades__status=S.VALIDATED, period__year=year).distinct().count(),
            "published_grades": grades.filter(status=S.PUBLISHED).count(),
            "guardians": guardians.count(),
            "guardians_active": guardians.filter(activated_at__isnull=False).count(),
            # Mise en route : ce qu'il manque pour que les enseignants puissent saisir.
            "setup": {
                "periods": Period.objects.filter(year=year).count(),
                "classrooms": Classroom.objects.filter(year=year).count(),
                "unassigned": ClassSubject.objects.filter(classroom__year=year,
                                                          teacher__isnull=True).count(),
            },
        })


class DirectionAssessmentsView(StaffView):
    permission_classes = [IsDirection]

    def get(self, request):
        wanted = request.query_params.get("state", S.SUBMITTED)
        year = current_year()
        qs = list(annotate_assessments(Assessment.objects.filter(period__year=year)).select_related(
            "class_subject__classroom", "class_subject__subject", "class_subject__teacher",
            "period").order_by("-updated_at"))
        qs = [a for a in qs if state_of(a) == wanted][:300]
        enrolled = enrolled_counts({a.class_subject.classroom_id for a in qs})
        items = []
        for assessment in qs:
            summary = assessment_summary(assessment,
                                         enrolled.get(assessment.class_subject.classroom_id, 0))
            summary.update({
                "classroom": assessment.class_subject.classroom.name,
                "subject": assessment.class_subject.subject.name,
                "teacher": assessment.class_subject.teacher.full_name
                if assessment.class_subject.teacher else "",
            })
            items.append(summary)
        return Response({"items": items})


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class AssessmentActionView(StaffView):
    permission_classes = [IsDirection]

    def post(self, request, pk, action):
        assessment = accessible_assessment(request, pk)
        grades = assessment.grades.all()
        if action == "validate":
            count = grades.filter(status=S.SUBMITTED).update(status=S.VALIDATED,
                                                              updated_at=timezone.now())
        elif action == "publish":
            count = publish_assessments([assessment])
        elif action == "return":
            data = ReasonSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            _set_reason(data.validated_data.get("reason") or "Renvoyé à l'enseignant")
            count = grades.filter(status__in=[S.SUBMITTED, S.VALIDATED]).update(
                status=S.DRAFT, updated_at=timezone.now())
        else:
            raise Http404
        if not count:
            return Response({"detail": "Aucune note dans l'état attendu."}, status=400)
        return Response({"changed": count})


class CorrectionSerializer(serializers.Serializer):
    value = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    is_absent = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=255, min_length=3)


class GradeCorrectView(StaffView):
    """Correction d'une note déjà envoyée : motif obligatoire, journal automatique, et le
    parent est prévenu si la note était publiée."""

    permission_classes = [IsDirection]

    def post(self, request, pk):
        grade = get_object_or_404(
            Grade.objects.select_related("assessment__class_subject__subject", "student"),
            pk=pk)
        if grade.status == S.DRAFT:
            return Response({"detail": "Une note en brouillon se modifie dans la grille."},
                            status=400)
        data = CorrectionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        value, error = parse_value(data.validated_data.get("value"), grade.assessment.max_score)
        if error:
            return Response({"detail": error}, status=400)
        absent = data.validated_data["is_absent"]
        if value is None and not absent:
            return Response({"detail": "Indiquez une note ou une absence."}, status=400)
        _set_reason(data.validated_data["reason"])
        old = grade.value
        grade.value, grade.is_absent = (None if absent else value), absent
        grade.revision += 1
        grade.save(update_fields=["value", "is_absent", "revision", "updated_at"])
        if grade.status == S.PUBLISHED:
            subject = grade.assessment.class_subject.subject.name
            new = "absent(e)" if absent else f"{value:g}"
            before = "absent(e)" if old is None else f"{old:g}"
            notify_guardians_of(
                {grade.student_id: grade.student}, Notification.Kind.CORRECTION,
                lambda s: (f"Note corrigée pour {s.first_name} en {subject} : {before} → {new}.",
                           f"/parent/enfant/{grade.school_id}/{s.pk}"),
            )
        return Response({"value": num(grade.value), "is_absent": grade.is_absent})


class GradeHistoryView(StaffView):
    permission_classes = [IsDirection]

    def get(self, request, pk):
        from apps.accounts.models import Membership

        names = dict(Membership.objects.values_list("user_id", "full_name"))
        entries = GradeAudit.objects.filter(grade_id=pk).order_by("created_at")
        return Response({"items": [{
            "at": e.created_at, "action": e.action,
            "old_value": num(e.old_value), "new_value": num(e.new_value),
            "old_status": STATUS_LABELS.get(e.old_status, e.old_status),
            "new_status": STATUS_LABELS.get(e.new_status, e.new_status),
            "old_is_absent": e.old_is_absent, "new_is_absent": e.new_is_absent,
            "by": names.get(e.actor_user_id, "—"), "reason": e.reason,
        } for e in entries]})


class DirectionClassesView(StaffView):
    permission_classes = [IsDirection]

    def get(self, request):
        year = current_year()
        return Response({"items": [{
            "id": str(c.pk), "name": c.name, "level": c.level.name,
            "students": active_enrollments(c).count(),
            "periods": [{"id": str(p.pk), "name": p.name} for p in periods_of(c)],
        } for c in Classroom.objects.filter(year=year).select_related("level")
            .order_by("level__rank", "name")]})


def _classroom_period(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk)
    periods = periods_of(classroom)
    period = periods.filter(pk=request.query_params.get("period")).first() if \
        request.query_params.get("period") else periods.first()
    if period is None:
        raise Http404
    return classroom, period


def _statuses(request):
    if request.query_params.get("scope") == "published":
        return [S.PUBLISHED]
    return [S.VALIDATED, S.PUBLISHED]


class ClassResultsView(StaffView):
    permission_classes = [IsDirection]

    def get(self, request, pk):
        classroom, period = _classroom_period(request, pk)
        results = compute_class_results(classroom, period, _statuses(request))
        students = sorted(results.students,
                          key=lambda s: (s.rank is None, s.rank or 0,
                                         s.enrollment.student.last_name))
        return Response({
            "classroom": classroom.name, "period": {"id": str(period.pk), "name": period.name},
            "max_score": num(results.rules.max_score),
            "class_average": num(results.class_average), "highest": num(results.highest),
            "lowest": num(results.lowest), "ranked": results.ranked_size,
            "to_publish": Assessment.objects.filter(
                class_subject__classroom=classroom, period=period,
                grades__status=S.VALIDATED).distinct().count(),
            "subjects": [{"id": str(s.class_subject.pk), "name": s.class_subject.subject.name,
                          "coefficient": num(s.coefficient),
                          "class_average": num(s.class_average)} for s in results.subjects],
            "students": [{
                "id": str(s.enrollment.student_id),
                "name": f"{s.enrollment.student.last_name} {s.enrollment.student.first_name}",
                "average": num(s.general), "rank": s.rank,
                "rank_label": ordinal(s.rank, s.tied), "appreciation": s.appreciation,
                "subjects": {str(k): num(v) for k, v in s.subject_averages.items()},
            } for s in students],
        })


class ClassPublishView(StaffView):
    permission_classes = [IsDirection]

    def post(self, request, pk):
        classroom, period = _classroom_period(request, pk)
        assessments = Assessment.objects.filter(
            class_subject__classroom=classroom, period=period, grades__status=S.VALIDATED
        ).distinct().select_related("class_subject__subject")
        count = publish_assessments(list(assessments))
        if not count:
            return Response({"detail": "Aucune note validée à publier."}, status=400)
        return Response({"published": count})


class ClassBulletinsView(StaffView):
    """Bulletin d'un seul élève : assez rapide pour être servi directement."""

    permission_classes = [IsDirection]

    def get(self, request, pk):
        classroom, period = _classroom_period(request, pk)
        only = request.query_params.get("student")
        if not only:
            raise Http404
        results = compute_class_results(classroom, period, _statuses(request))
        pages = build_pages(results, classroom, period,
                            {s.enrollment.student_id for s in results.students
                             if str(s.enrollment.student_id) == only})
        pdf = render_pdf(request.school, pages,
                         draft=request.query_params.get("scope") != "published")
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="bulletin.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class ClassBulletinsJobView(StaffView):
    """Bulletins de toute une classe : 60 élèves dépassent largement le délai d'une requête."""

    permission_classes = [IsDirection]

    def post(self, request, pk):
        from apps.documents import jobs
        from apps.documents.tasks import class_bulletins

        classroom, period = _classroom_period(request, pk)
        scope = "published" if request.query_params.get("scope") == "published" else "all"
        job_id = jobs.start(
            class_bulletins, user_id=request.user.pk, school_id=request.school.pk,
            filename=f"bulletins-{classroom.name}-{period.name}.pdf".replace(" ", "-"),
            classroom_id=str(classroom.pk), period_id=str(period.pk), scope=scope)
        return Response({"job": job_id}, status=status.HTTP_202_ACCEPTED)


class ClassReleaseView(StaffView):
    """Publication des bulletins d'une classe : c'est elle qui ouvre aux parents la moyenne
    générale, le rang et le bulletin PDF."""

    permission_classes = [IsDirection]

    def get(self, request, pk):
        classroom, period = _classroom_period(request, pk)
        return Response(releases.status(classroom, period))

    def post(self, request, pk):
        classroom, period = _classroom_period(request, pk)
        state = releases.status(classroom, period)
        if state["blockers"]:
            return Response({"detail": "Des évaluations ne sont pas prêtes.",
                             "blockers": state["blockers"]}, status=400)
        if not state["assessments"]:
            return Response({"detail": "Aucune évaluation sur cette période."}, status=400)
        count = releases.release(classroom, period, request.user.pk)
        return Response({"released": count, **releases.status(classroom, period)})

    def delete(self, request, pk):
        classroom, period = _classroom_period(request, pk)
        releases.withdraw(classroom, period)
        return Response(releases.status(classroom, period))
