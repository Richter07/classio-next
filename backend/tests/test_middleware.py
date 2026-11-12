import pytest
from django.http import JsonResponse
from django.test import RequestFactory

from apps.accounts.models import Membership, User
from apps.students.models import Student
from apps.tenancy.context import tenant_context
from apps.tenancy.middleware import TenantMiddleware, school_slug_from_host
from apps.tenancy.models import School

from .conftest import as_app_role

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _domain(settings):
    settings.BASE_DOMAIN = "classio.test"
    settings.ALLOWED_HOSTS = ["*"]


@pytest.mark.parametrize(
    ("host", "slug"),
    [
        ("ecole-x.classio.test", "ecole-x"),
        ("ecole-x.classio.test:8000", "ecole-x"),
        ("app.classio.test", None),
        ("classio.test", None),
        ("a.b.classio.test", None),
        ("ecole-x.evil.test", None),
    ],
)
def test_slug_resolution(host, slug):
    assert school_slug_from_host(host) == slug


def call(host, user=None, view=None):
    from django.contrib.auth.models import AnonymousUser

    request = RequestFactory().get("/", HTTP_HOST=host)
    request.user = user or AnonymousUser()
    return TenantMiddleware(view or (lambda r: JsonResponse({"ok": True})))(request)


class TestAccess:
    def test_unknown_school_is_404(self):
        assert call("inconnue.classio.test").status_code == 404

    def test_suspended_school_is_403(self, school_a):
        School.objects.filter(pk=school_a["school"].pk).update(status="SUSPENDED")
        assert call("ecole-a.classio.test").status_code == 403

    def test_user_of_another_school_is_refused(self, school_a):
        stranger = User.objects.create_user("+2290195000002")
        assert call("ecole-a.classio.test", stranger).status_code == 403

    def test_member_gets_the_school_context(self, school_a):
        teacher = User.objects.create_user("+2290195000003")
        with tenant_context(school_a["school"].pk):
            Membership.objects.create(user=teacher, role="TEACHER", full_name="Prof")

        seen = {}

        def view(request):
            seen["count"] = Student.objects.count()
            return JsonResponse({})

        with as_app_role():
            assert call("ecole-a.classio.test", teacher, view).status_code == 200
        assert seen["count"] == 1

    def test_error_response_rolls_back_writes(self, school_a):
        teacher = User.objects.create_user("+2290195000004")
        with tenant_context(school_a["school"].pk):
            Membership.objects.create(user=teacher, role="TEACHER", full_name="Prof")

        def view(request):
            Student.objects.update(first_name="écrasé")
            return JsonResponse({}, status=400)

        from django.db import transaction

        with transaction.atomic(), as_app_role():  # savepoint interne du test
            call("ecole-a.classio.test", teacher, view)
        school_a["student"].refresh_from_db()
        assert school_a["student"].first_name != "écrasé"
