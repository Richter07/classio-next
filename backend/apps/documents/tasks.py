"""Tâches Celery. Chacune ouvre son propre contexte d'école : sans lui, le RLS ne lui montrerait
aucune ligne (c'est voulu, cf. apps/tenancy/context.py)."""

import logging
from datetime import timedelta
from uuid import UUID

from celery import shared_task
from django.utils import timezone

from apps.tenancy.context import tenant_context
from apps.tenancy.models import School

from . import jobs

log = logging.getLogger("classio.documents")


@shared_task
def class_bulletins(job_id, user_id, school_id, classroom_id, period_id, scope, student_id=None):
    from apps.academics.models import Classroom, Period
    from apps.grades.bulletin import build_pages, render_pdf
    from apps.grades.calculations import compute_class_results
    from apps.grades.models import Grade

    try:
        with tenant_context(UUID(school_id), UUID(user_id)):
            classroom = Classroom.objects.get(pk=classroom_id)
            period = Period.objects.get(pk=period_id)
            statuses = ([Grade.Status.PUBLISHED] if scope == "published"
                        else [Grade.Status.VALIDATED, Grade.Status.PUBLISHED])
            results = compute_class_results(classroom, period, statuses)
            only = {UUID(student_id)} if student_id else None
            pages = build_pages(results, classroom, period, only)
            pdf = render_pdf(School.objects.get(pk=school_id), pages, draft=scope != "published")
        jobs.finish(job_id, pdf)
    except Exception:
        log.exception("Échec de génération des bulletins (travail %s)", job_id)
        jobs.finish(job_id, error="La génération a échoué.")


@shared_task
def access_letters(job_id, user_id, school_id, guardian_ids, reissue_activated=False):
    from apps.documents.letters import build_letters
    from apps.students.models import Guardian

    try:
        with tenant_context(UUID(school_id), UUID(user_id)):
            guardians = list(Guardian.objects.filter(pk__in=guardian_ids).select_related("user")
                             .prefetch_related("students").order_by("full_name"))
            pdf = build_letters(School.objects.get(pk=school_id), guardians, UUID(user_id),
                                reissue_activated)
        jobs.finish(job_id, pdf)
    except Exception:
        log.exception("Échec de génération des lettres d'accès (travail %s)", job_id)
        jobs.finish(job_id, error="La génération a échoué.")


@shared_task
def purge_expired():
    """Durées de conservation : rien ne doit traîner plus longtemps que nécessaire."""
    from apps.accounts.models import AccessCode
    from apps.notifications.models import Notification
    from apps.students.models import ImportBatch

    now = timezone.now()
    codes = AccessCode.objects.filter(expires_at__lt=now - timedelta(days=30)).delete()[0]
    notifications = imports = 0
    for school_id in School.objects.values_list("pk", flat=True):
        with tenant_context(school_id):
            notifications += Notification.objects.filter(
                created_at__lt=now - timedelta(days=400)).delete()[0]
            # Un import contrôlé mais jamais appliqué garde les données des élèves : 7 jours.
            imports += ImportBatch.objects.filter(
                status=ImportBatch.Status.CHECKED, created_at__lt=now - timedelta(days=7)
            ).delete()[0]
    log.info("Purge : %s codes, %s notifications, %s imports", codes, notifications, imports)
    return {"codes": codes, "notifications": notifications, "imports": imports}
