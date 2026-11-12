"""Publication des bulletins d'une classe pour une période, décidée par la direction.

Tant que la direction n'a pas publié, les parents voient les notes publiées une à une, mais ni
moyenne générale, ni rang, ni bulletin. À la publication, chaque bulletin est figé
(ReportCard.snapshot) : changer ensuite un coefficient ou corriger une note ne modifie pas un
bulletin déjà remis aux familles. Pour en tenir compte, la direction publie à nouveau.
"""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.academics.models import ClassSubject
from apps.notifications.models import Notification
from apps.notifications.services import notify_guardians_of

from .bulletin import build_pages
from .calculations import compute_class_results
from .models import Assessment, Grade, ReportCard

S = Grade.Status


def _enrollments(classroom):
    from apps.students.models import Enrollment

    return Enrollment.objects.filter(classroom=classroom).exclude(status=Enrollment.Status.LEFT)


def status(classroom, period) -> dict:
    """Ce qui empêche de publier, et ce qui mérite l'attention de la direction."""
    enrolled = _enrollments(classroom).count()
    assessments = (
        Assessment.objects.filter(class_subject__classroom=classroom, period=period)
        .select_related("class_subject__subject")
        .annotate(
            n_published=Count("grades", filter=Q(grades__status=S.PUBLISHED)),
            n_grades=Count("grades", filter=Q(grades__value__isnull=False)
                           | Q(grades__is_absent=True)),
        )
        .order_by("class_subject__subject__name", "held_on")
    )
    blockers = []
    for a in assessments:
        label = f"{a.class_subject.subject.name} · {a.title or a.get_kind_display()}"
        if a.n_published < a.n_grades or a.n_grades == 0:
            blockers.append(f"{label} : notes pas encore publiées")
        elif a.n_grades < enrolled:
            blockers.append(f"{label} : {enrolled - a.n_grades} élève(s) sans note")
    used = {a.class_subject_id for a in assessments}
    without = [cs.subject.name for cs in ClassSubject.objects.filter(classroom=classroom)
               .select_related("subject").order_by("subject__name") if cs.pk not in used]
    cards = ReportCard.objects.filter(enrollment__classroom=classroom, period=period,
                                      published_at__isnull=False)
    released = cards.order_by("-published_at").values_list("published_at", flat=True).first()
    return {
        "released_at": released,
        "released_count": cards.count(),
        "enrolled": enrolled,
        "assessments": len(assessments),
        "blockers": blockers,
        "subjects_without_grades": without,
        # Une note corrigée après la publication : le bulletin figé ne la reflète pas encore.
        "outdated": bool(released) and Grade.objects.filter(
            assessment__class_subject__classroom=classroom, assessment__period=period,
            updated_at__gt=released).exists(),
    }


@transaction.atomic
def release(classroom, period, user_id) -> int:
    results = compute_class_results(classroom, period, [S.PUBLISHED])
    pages = {page["student_id"]: page for page in build_pages(results, classroom, period)}
    now = timezone.now()
    students = {}
    for s in results.students:
        page = pages[str(s.enrollment.student_id)]
        page["released_on"] = now.date().isoformat()
        ReportCard.objects.update_or_create(
            enrollment=s.enrollment, period=period,
            defaults={
                "general_average": s.general, "rank": s.rank, "is_tied": s.tied,
                "class_size": results.ranked_size, "class_average": results.class_average,
                "highest_average": results.highest, "lowest_average": results.lowest,
                "appreciation": s.appreciation, "snapshot": page, "published_at": now,
                "published_by_user_id": user_id,
            },
        )
        students[s.enrollment.student_id] = s.enrollment.student

    school_id = classroom.school_id

    def message(student):
        return (f"Le bulletin de {student.first_name} ({period.name}) est disponible.",
                f"/parent/enfant/{school_id}/{student.pk}")

    notify_guardians_of(students, Notification.Kind.REPORT_CARD, message)
    return len(students)


def withdraw(classroom, period) -> int:
    return ReportCard.objects.filter(enrollment__classroom=classroom, period=period).update(
        published_at=None)


def released_card(enrollment, period):
    return ReportCard.objects.filter(enrollment=enrollment, period=period,
                                     published_at__isnull=False).first()
