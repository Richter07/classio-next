"""Envoi des notifications.

Pas de SMS ni de WhatsApp pour l'instant (choix économique) : la notification est visible dans
l'application (« Nouveautés »), et le sera aussi en push quand celui-ci sera branché.

Les journaux ne contiennent jamais le contenu d'une notification ni un numéro de téléphone : ce
sont des données de mineurs. En développement seulement, le message s'affiche dans la console.
"""

import logging

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import PushSubscription
from apps.students.models import Guardian

from .models import Notification

log = logging.getLogger("classio.notifications")


def _channel(guardian: Guardian) -> str:
    if PushSubscription.objects.filter(user_id=guardian.user_id).exists():
        return Notification.Channel.PUSH
    return Notification.Channel.IN_APP


def deliver(notification: Notification) -> None:
    if settings.DEBUG:
        log.warning("[DEV %s] %s", notification.channel, notification.message)
    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.save(update_fields=["status", "sent_at"])


def notify_guardians_of(students: dict, kind: str, message_for) -> int:
    """students : {student_id: Student}. message_for(student) -> (message, link)."""
    links = Guardian.students.through.objects.filter(student_id__in=students).select_related(
        "guardian"
    )
    created = 0
    for link in links:
        student = students[link.student_id]
        message, path = message_for(student)
        notification = Notification.objects.create(
            guardian=link.guardian, student=student, kind=kind,
            channel=_channel(link.guardian), message=message[:255], link=path,
        )
        deliver(notification)
        created += 1
    return created
