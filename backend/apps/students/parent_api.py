"""Espace parent. Le parent n'a pas d'école « courante » : chaque vue ouvre le contexte de
l'école de l'enfant, et ne montre que des notes publiées."""

from django.db.models import Q
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import ClassSubject, LevelSubject, Period
from apps.grades.bulletin import KIND_LABELS, render_pdf
from apps.grades.models import Grade, ReportCard
from apps.grades.release import released_card
from apps.notifications.models import Notification
from apps.tenancy.context import tenant_context
from apps.tenancy.models import School
from apps.tenancy.permissions import SessionAuth

from .models import Enrollment, Guardian, Student

PUBLISHED = [Grade.Status.PUBLISHED]


class ParentView(APIView):
    authentication_classes = [SessionAuth]
    permission_classes = [IsAuthenticated]

    def school_ids(self):
        with tenant_context(user_id=self.request.user.pk):
            return list(
                Guardian.objects.filter(user=self.request.user)
                .values_list("school_id", flat=True).distinct()
            )

    def child(self, student_id) -> Student:
        student = Student.objects.filter(pk=student_id, guardians__user=self.request.user).first()
        if student is None:
            raise Http404
        return student


def periods_for(enrollment):
    return list(Period.objects.filter(year=enrollment.year).filter(
        Q(level__isnull=True) | Q(level_id=enrollment.classroom.level_id)))


def current_period(periods, results_has_grades):
    today = timezone.localdate()
    ordered = sorted(periods, key=lambda p: p.rank)
    for period in ordered:
        if period.starts_on <= today <= period.ends_on and results_has_grades(period):
            return period
    with_grades = [p for p in ordered if results_has_grades(p)]
    return with_grades[-1] if with_grades else (ordered[0] if ordered else None)


def _has_published(enrollment):
    def check(period):
        return Grade.objects.filter(
            student_id=enrollment.student_id, assessment__period=period, status__in=PUBLISHED,
            assessment__class_subject__classroom=enrollment.classroom,
        ).exists()
    return check


def _current_enrollment(student, year_id=None):
    enrollments = Enrollment.objects.filter(student=student).select_related(
        "classroom", "classroom__level", "year"
    )
    if year_id:
        return enrollments.filter(year_id=year_id).first()
    return enrollments.filter(year__is_current=True).first() or enrollments.order_by(
        "-year__starts_on").first()


def _num(text):
    """« 12,50 » (texte du bulletin figé) -> 12.5 ; « — » -> None."""
    if not text or text in ("—", "Abs"):
        return None
    return float(text.replace(",", "."))


def _dated(page):
    from datetime import date

    page = dict(page)
    if page.get("released_on"):
        page["released_on"] = date.fromisoformat(page["released_on"])
    return page


def _grade_payload(grade):
    return {
        "id": str(grade.pk),
        "subject": grade.assessment.class_subject.subject.name,
        "kind": KIND_LABELS[grade.assessment.kind],
        "title": grade.assessment.title,
        "date": grade.assessment.held_on,
        "value": grade.value,
        "max_score": grade.assessment.max_score,
        "is_absent": grade.is_absent,
        "published_at": grade.published_at,
    }


class ChildrenView(ParentView):
    def get(self, request):
        children = []
        for school_id in self.school_ids():
            with tenant_context(school_id, request.user.pk):
                school = School.objects.get(pk=school_id)
                for student in Student.objects.filter(guardians__user=request.user).distinct():
                    enrollment = _current_enrollment(student)
                    item = {
                        "id": str(student.pk), "school_id": str(school.pk),
                        "first_name": student.first_name, "last_name": student.last_name,
                        "school": {"name": school.name, "color": school.color_primary},
                        "classroom": enrollment.classroom.name if enrollment else None,
                        "last_grade": None, "average": None, "period": None,
                    }
                    last = (
                        Grade.objects.filter(student=student, status__in=PUBLISHED)
                        .select_related("assessment__class_subject__subject")
                        .order_by("-published_at").first()
                    )
                    if last:
                        item["last_grade"] = _grade_payload(last)
                    if enrollment:
                        # Moyenne affichée : celle du dernier bulletin publié par l'école.
                        card = ReportCard.objects.filter(
                            enrollment=enrollment, published_at__isnull=False
                        ).select_related("period").order_by("-period__rank").first()
                        if card:
                            item["period"] = card.period.name
                            item["average"] = card.general_average
                    children.append(item)
        return Response({"children": children})


class ChildDetailView(ParentView):
    def get(self, request, school_id, student_id):
        if school_id not in self.school_ids():
            raise Http404
        with tenant_context(school_id, request.user.pk):
            student = self.child(student_id)
            enrollments = list(
                Enrollment.objects.filter(student=student)
                .select_related("classroom", "year").order_by("-year__starts_on")
            )
            enrollment = _current_enrollment(student, request.query_params.get("year"))
            if enrollment is None:
                raise Http404
            periods = sorted(periods_for(enrollment), key=lambda p: p.rank)
            selected = next(
                (p for p in periods if str(p.pk) == request.query_params.get("period")), None
            ) or current_period(periods, _has_published(enrollment))

            body = {
                "student": {"id": str(student.pk), "first_name": student.first_name,
                            "last_name": student.last_name, "matricule": student.matricule},
                "school": {"id": str(school_id),
                           "name": School.objects.get(pk=school_id).name},
                "classroom": enrollment.classroom.name,
                "year": {"id": str(enrollment.year_id), "label": enrollment.year.label},
                "years": [{"id": str(e.year_id), "label": e.year.label,
                           "classroom": e.classroom.name} for e in enrollments],
                "periods": [{"id": str(p.pk), "name": p.name} for p in periods],
                "period": None, "summary": None, "subjects": [],
            }
            if selected is None:
                return Response(body)

            grades = (
                Grade.objects.filter(student=student, assessment__period=selected,
                                     status__in=PUBLISHED,
                                     assessment__class_subject__classroom=enrollment.classroom)
                .select_related("assessment__class_subject__subject")
                .order_by("assessment__held_on", "assessment__created_at")
            )
            by_subject = {}
            for grade in grades:
                by_subject.setdefault(grade.assessment.class_subject_id, []).append(
                    _grade_payload(grade))

            # Moyennes et rangs : seulement quand la direction a publié le bulletin, et tels
            # qu'ils y figurent (figés).
            card = released_card(enrollment, selected)
            page = card.snapshot if card else None
            rows = {row.get("id"): row for row in (page or {}).get("rows", [])}
            body["period"] = {"id": str(selected.pk), "name": selected.name}
            body["released"] = card is not None
            body["has_bulletin"] = card is not None
            if card:
                body["summary"] = {
                    "average": card.general_average, "rank": card.rank, "tied": card.is_tied,
                    "rank_label": page.get("rank", ""), "class_size": card.class_size,
                    "class_average": card.class_average, "highest": card.highest_average,
                    "lowest": card.lowest_average, "appreciation": card.appreciation,
                    "max_score": page.get("max_score", "20").replace(",", "."),
                    "released_at": card.published_at,
                }
            level_coefficients = dict(LevelSubject.objects.filter(
                level_id=enrollment.classroom.level_id).values_list("subject_id", "coefficient"))
            body["subjects"] = [
                {
                    "id": str(cs.pk),
                    "name": cs.subject.name,
                    "teacher": cs.teacher.full_name if cs.teacher else "",
                    "coefficient": cs.coefficient or level_coefficients.get(cs.subject_id) or 1,
                    "average": _num(rows.get(str(cs.pk), {}).get("average")),
                    "class_average": _num(rows.get(str(cs.pk), {}).get("class_average")),
                    "rank_label": rows.get(str(cs.pk), {}).get("rank"),
                    "grades": by_subject.get(cs.pk, []),
                }
                for cs in ClassSubject.objects.filter(classroom=enrollment.classroom)
                .select_related("subject", "teacher").order_by("subject__name")
            ]
        return Response(body)


class ChildBulletinView(ParentView):
    def get(self, request, school_id, student_id):
        if school_id not in self.school_ids():
            raise Http404
        with tenant_context(school_id, request.user.pk):
            student = self.child(student_id)
            enrollment = _current_enrollment(student, request.query_params.get("year"))
            period = Period.objects.filter(pk=request.query_params.get("period")).first()
            if enrollment is None or period is None:
                raise Http404
            # Uniquement un bulletin publié par la direction, tel qu'il a été figé.
            card = released_card(enrollment, period)
            if card is None:
                raise Http404
            pdf = render_pdf(School.objects.get(pk=school_id), [_dated(card.snapshot)])
        response = HttpResponse(pdf, content_type="application/pdf")
        name = f"bulletin-{student.last_name}-{student.first_name}-{period.name}".replace(" ", "-")
        response["Content-Disposition"] = f'attachment; filename="{name}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class NotificationsView(ParentView):
    def get(self, request):
        items = []
        unread = 0
        for school_id in self.school_ids():
            with tenant_context(school_id, request.user.pk):
                school = School.objects.get(pk=school_id)
                rows = Notification.objects.filter(guardian__user=request.user).select_related(
                    "student").order_by("-created_at")[:40]
                unread += Notification.objects.filter(
                    guardian__user=request.user, read_at__isnull=True).count()
                items += [{
                    "id": str(n.pk), "kind": n.kind, "message": n.message, "link": n.link,
                    "created_at": n.created_at, "read": n.read_at is not None,
                    "school": school.name,
                    "student": n.student.first_name if n.student else None,
                } for n in rows]
        items.sort(key=lambda n: n["created_at"], reverse=True)
        return Response({"items": items[:40], "unread": unread})

    def post(self, request):
        for school_id in self.school_ids():
            with tenant_context(school_id, request.user.pk):
                Notification.objects.filter(
                    guardian__user=request.user, read_at__isnull=True,
                    status__in=[Notification.Status.SENT, Notification.Status.DELIVERED,
                                Notification.Status.QUEUED],
                ).update(read_at=timezone.now(), status=Notification.Status.READ)
        return Response({"unread": 0})

