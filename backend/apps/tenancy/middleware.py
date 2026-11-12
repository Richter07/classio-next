from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse

from apps.accounts.models import Membership
from apps.students.models import Guardian

from .context import tenant_context
from .models import School

SESSION_SCHOOL_KEY = "school_id"


def school_slug_from_host(host: str) -> str | None:
    """``ecole-x.<BASE_DOMAIN>`` donne ``ecole-x`` ; le domaine nu et ``app.`` n'ont pas d'école."""
    host = host.split(":")[0].lower()
    suffix = f".{settings.BASE_DOMAIN}"
    if not host.endswith(suffix):
        return None
    slug = host[: -len(suffix)]
    return None if "." in slug or slug in {"app", "www", "api"} else slug


@dataclass
class SchoolAccess:
    memberships: list = field(default_factory=list)
    is_guardian: bool = False

    @property
    def roles(self) -> frozenset:
        return frozenset(m.role for m in self.memberships)

    def __bool__(self):
        return bool(self.memberships) or self.is_guardian


def school_access(user, school: School) -> SchoolAccess:
    # Ces deux tables exposent à l'utilisateur ses propres lignes via app.user_id.
    with tenant_context(user_id=user.pk):
        return SchoolAccess(
            memberships=list(
                Membership.objects.filter(school=school, user=user, is_active=True)
            ),
            is_guardian=Guardian.objects.filter(school=school, user=user).exists(),
        )


class TenantMiddleware:
    """Détermine l'école de la requête et l'enveloppe dans son contexte RLS.

    L'école vient du sous-domaine (production) ou, à défaut, de la session : c'est le
    « champ d'identification à la connexion » du cahier des charges, qui permet aussi de
    tester depuis un téléphone sur le réseau local. Dans les deux cas, le contexte d'école
    n'est accordé qu'à un utilisateur authentifié et rattaché à cette école.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.school = None
        request.roles = frozenset()
        request.memberships = []
        request.is_guardian_here = False
        user = request.user if request.user.is_authenticated else None

        slug = school_slug_from_host(request.get_host())
        school = None
        if slug:
            school = School.objects.filter(slug=slug).first()
            if school is None:
                return JsonResponse({"detail": "École inconnue."}, status=404)
        elif user and (school_id := request.session.get(SESSION_SCHOOL_KEY)):
            school = School.objects.filter(pk=school_id).first()

        if school and school.status == School.Status.SUSPENDED:
            return JsonResponse({"detail": "Espace suspendu."}, status=403)

        school_id = None
        if school:
            request.school = school
            if user:
                access = school_access(user, school)
                if access:
                    school_id = school.pk
                    request.roles = access.roles
                    request.memberships = access.memberships
                    request.is_guardian_here = access.is_guardian
                elif slug:
                    return JsonResponse({"detail": "Accès refusé à cette école."}, status=403)
                else:
                    request.session.pop(SESSION_SCHOOL_KEY, None)
                    request.school = None

        with tenant_context(school_id=school_id, user_id=user.pk if user else None):
            response = self.get_response(request)
            # Django convertit les exceptions de vue en réponse : sans cela, on validerait
            # une écriture partielle.
            if response.status_code >= 400:
                transaction.set_rollback(True)
        return response
