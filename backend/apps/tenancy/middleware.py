from django.conf import settings
from django.db import transaction
from django.http import JsonResponse

from apps.accounts.models import Membership
from apps.students.models import Guardian

from .context import tenant_context
from .models import School


def school_slug_from_host(host: str) -> str | None:
    """``ecole-x.<BASE_DOMAIN>`` donne ``ecole-x`` ; le domaine nu et ``app.`` n'ont pas d'école."""
    host = host.split(":")[0].lower()
    suffix = f".{settings.BASE_DOMAIN}"
    if not host.endswith(suffix):
        return None
    slug = host[: -len(suffix)]
    return None if "." in slug or slug in {"app", "www", "api"} else slug


def _user_belongs_to(user, school: School) -> bool:
    # Ces deux tables exposent à l'utilisateur ses propres lignes via app.user_id.
    with tenant_context(user_id=user.pk):
        return (
            Membership.objects.filter(school=school, user=user, is_active=True).exists()
            or Guardian.objects.filter(school=school, user=user).exists()
        )


class TenantMiddleware:
    """Résout l'école depuis le sous-domaine et enveloppe la requête dans son contexte.

    Le contexte d'école n'est accordé qu'à un utilisateur authentifié et rattaché à cette
    école : le sous-domaine seul, qui se falsifie via l'en-tête Host, n'ouvre aucune donnée.
    Sur le domaine sans école (espace parent multi-écoles, super-admin), seul user_id est posé
    et chaque vue ouvre explicitement ``tenant_context`` école par école.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        slug = school_slug_from_host(request.get_host())
        request.school = None
        user = request.user if request.user.is_authenticated else None

        if slug:
            request.school = School.objects.filter(slug=slug).first()
            if request.school is None:
                return JsonResponse({"detail": "École inconnue."}, status=404)
            if request.school.status == School.Status.SUSPENDED:
                return JsonResponse({"detail": "Espace suspendu."}, status=403)

        school_id = None
        if request.school and user:
            if not _user_belongs_to(user, request.school):
                return JsonResponse({"detail": "Accès refusé à cette école."}, status=403)
            school_id = request.school.pk

        with tenant_context(school_id=school_id, user_id=user.pk if user else None):
            response = self.get_response(request)
            # Django convertit les exceptions de vue en réponse : sans cela, on validerait
            # une écriture partielle.
            if response.status_code >= 400:
                transaction.set_rollback(True)
        return response
