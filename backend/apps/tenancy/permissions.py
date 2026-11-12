from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission

from apps.accounts.models import Membership

Role = Membership.Role


class SessionAuth(SessionAuthentication):
    """Renvoie 401 (et non 403) quand la session manque : le client sait qu'il doit se
    reconnecter, au lieu de croire à un refus de droits."""

    def authenticate_header(self, request):
        return "Session"


def roles_allowed(*roles):
    class HasRole(BasePermission):
        message = "Votre rôle ne permet pas cette action."

        def has_permission(self, request, view):
            return bool(request.user.is_authenticated and set(roles) & request.roles)

    return HasRole


IsTeacher = roles_allowed(Role.TEACHER, Role.DIRECTOR, Role.CENSOR)
IsDirection = roles_allowed(Role.DIRECTOR, Role.CENSOR)
IsOffice = roles_allowed(Role.SECRETARY, Role.DIRECTOR)
IsStaff = roles_allowed(*Role.values)


def teacher_membership_ids(request) -> list:
    return [m.pk for m in request.memberships if m.role == Role.TEACHER]


def is_direction(request) -> bool:
    return bool({Role.DIRECTOR, Role.CENSOR} & request.roles)
